// skills.ts
import { realpath } from 'fs/promises'
import ignore from 'ignore'
import memoize from 'lodash-es/memoize.js'
import {
  basename,
  dirname,
  isAbsolute,
  join,
  sep as pathSep,
  relative,
} from 'path'
import {
  getAdditionalDirectoriesForClaudeMd,
  getSessionId,
} from '../bootstrap/state.js'
import {
  type AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
  logEvent,
} from '../services/analytics/index.js'
import { roughTokenCountEstimation } from '../services/tokenEstimation.js'
import type { Command, PromptCommand } from '../types/command.js'
import {
  parseArgumentNames,
  substituteArguments,
} from '../utils/argumentSubstitution.js'
import { logForDebugging } from '../utils/debug.js'
import {
  EFFORT_LEVELS,
  type EffortValue,
  parseEffortValue,
} from '../utils/effort.js'
import {
  getClaudeConfigHomeDir,
  isBareMode,
  isEnvTruthy,
} from '../utils/envUtils.js'
import { isENOENT, isFsInaccessible } from '../utils/errors.js'
import {
  coerceDescriptionToString,
  type FrontmatterData,
  type FrontmatterShell,
  parseBooleanFrontmatter,
  parseFrontmatter,
  parseShellFrontmatter,
  splitPathInFrontmatter,
} from '../utils/frontmatterParser.js'
import { getFsImplementation } from '../utils/fsOperations.js'
import { isPathGitignored } from '../utils/git/gitignore.js'
import { logError } from '../utils/log.js'
import {
  extractDescriptionFromMarkdown,
  getProjectDirsUpToHome,
  loadMarkdownFilesForSubdir,
  type MarkdownFile,
  parseSlashCommandToolsFromFrontmatter,
} from '../utils/markdownConfigLoader.js'
import { parseUserSpecifiedModel } from '../utils/model/model.js'
import { executeShellCommandsInPrompt } from '../utils/promptShellExecution.js'
import type { SettingSource } from '../utils/settings/constants.js'
import { isSettingSourceEnabled } from '../utils/settings/constants.js'
import { getManagedFilePath } from '../utils/settings/managedPath.js'
import { isRestrictedToPluginOnly } from '../utils/settings/pluginOnlyPolicy.js'
import { HooksSchema, type HooksSettings } from '../utils/settings/types.js'
import { createSignal } from '../utils/signal.js'
import { registerMCPSkillBuilders } from './mcpSkillBuilders.js'

export type LoadedFrom =
  | 'commands_DEPRECATED'
  | 'skills'
  | 'plugin'
  | 'managed'
  | 'bundled'
  | 'mcp'

// ────────────────────────────────────────────────────────────────────────────
// Caches (isolados neste módulo)
// ────────────────────────────────────────────────────────────────────────────

/**
 * Cache para resultados de realpath, evitando chamadas repetidas.
 */
const realpathCache = new Map<string, string>()

/**
 * Retorna um identificador canônico para um arquivo (resolvendo symlinks).
 * Usa cache para evitar repetir realpath.
 */
async function getFileIdentity(filePath: string): Promise<string | null> {
  if (realpathCache.has(filePath)) {
    const cached = realpathCache.get(filePath)
    return cached === '' ? null : cached
  }
  try {
    const resolved = await realpath(filePath)
    realpathCache.set(filePath, resolved)
    return resolved
  } catch {
    realpathCache.set(filePath, '')
    return null
  }
}

// ────────────────────────────────────────────────────────────────────────────
// Funções auxiliares de caminho e nomes
// ────────────────────────────────────────────────────────────────────────────

/**
 * Retorna o caminho base para skills de uma determinada fonte.
 */
export function getSkillsPath(
  source: SettingSource | 'plugin',
  dir: 'skills' | 'commands',
): string {
  switch (source) {
    case 'policySettings':
      return join(getManagedFilePath(), '.claude', dir)
    case 'userSettings':
      return join(getClaudeConfigHomeDir(), dir)
    case 'projectSettings':
      return `.claude/${dir}`
    case 'plugin':
      return 'plugin'
    default:
      return ''
  }
}

/**
 * Estimativa de tokens do frontmatter de uma skill.
 */
export function estimateSkillFrontmatterTokens(skill: Command): number {
  if (skill.type !== 'prompt') return 0
  const frontmatterText = [skill.name, skill.description, skill.whenToUse]
    .filter(Boolean)
    .join(' ')
  return roughTokenCountEstimation(frontmatterText)
}

// ────────────────────────────────────────────────────────────────────────────
// Parsing de frontmatter (compartilhado entre skills e MCP)
// ────────────────────────────────────────────────────────────────────────────

function parseHooksFromFrontmatter(
  frontmatter: FrontmatterData,
  skillName: string,
): HooksSettings | undefined {
  if (!frontmatter.hooks) return undefined
  const result = HooksSchema().safeParse(frontmatter.hooks)
  if (!result.success) {
    logForDebugging(
      `Invalid hooks in skill '${skillName}': ${result.error.message}`,
    )
    return undefined
  }
  return result.data
}

function parseSkillPaths(frontmatter: FrontmatterData): string[] | undefined {
  if (!frontmatter.paths) return undefined
  const patterns = splitPathInFrontmatter(frontmatter.paths)
    .map(p => (p.endsWith('/**') ? p.slice(0, -3) : p))
    .filter(p => p.length > 0)
  if (patterns.length === 0 || patterns.every(p => p === '**')) return undefined
  return patterns
}

/**
 * Parses all skill frontmatter fields that are shared between file-based and
 * MCP skill loading.
 */
export function parseSkillFrontmatterFields(
  frontmatter: FrontmatterData,
  markdownContent: string,
  resolvedName: string,
  descriptionFallbackLabel: 'Skill' | 'Custom command' = 'Skill',
): {
  displayName: string | undefined
  description: string
  hasUserSpecifiedDescription: boolean
  allowedTools: string[]
  argumentHint: string | undefined
  argumentNames: string[]
  whenToUse: string | undefined
  version: string | undefined
  model: ReturnType<typeof parseUserSpecifiedModel> | undefined
  disableModelInvocation: boolean
  userInvocable: boolean
  hooks: HooksSettings | undefined
  executionContext: 'fork' | undefined
  agent: string | undefined
  effort: EffortValue | undefined
  shell: FrontmatterShell | undefined
} {
  const validatedDescription = coerceDescriptionToString(
    frontmatter.description,
    resolvedName,
  )
  const description =
    validatedDescription ??
    extractDescriptionFromMarkdown(markdownContent, descriptionFallbackLabel)

  const userInvocable =
    frontmatter['user-invocable'] === undefined
      ? true
      : parseBooleanFrontmatter(frontmatter['user-invocable'])

  const model =
    frontmatter.model === 'inherit'
      ? undefined
      : frontmatter.model
        ? parseUserSpecifiedModel(frontmatter.model as string)
        : undefined

  const effortRaw = frontmatter['effort']
  const effort =
    effortRaw !== undefined ? parseEffortValue(effortRaw) : undefined
  if (effortRaw !== undefined && effort === undefined) {
    logForDebugging(
      `Skill ${resolvedName} has invalid effort '${effortRaw}'. Valid options: ${EFFORT_LEVELS.join(', ')} or an integer`,
    )
  }

  return {
    displayName:
      frontmatter.name != null ? String(frontmatter.name) : undefined,
    description,
    hasUserSpecifiedDescription: validatedDescription !== null,
    allowedTools: parseSlashCommandToolsFromFrontmatter(
      frontmatter['allowed-tools'],
    ),
    argumentHint:
      frontmatter['argument-hint'] != null
        ? String(frontmatter['argument-hint'])
        : undefined,
    argumentNames: parseArgumentNames(
      frontmatter.arguments as string | string[] | undefined,
    ),
    whenToUse: frontmatter.when_to_use as string | undefined,
    version: frontmatter.version as string | undefined,
    model,
    disableModelInvocation: parseBooleanFrontmatter(
      frontmatter['disable-model-invocation'],
    ),
    userInvocable,
    hooks: parseHooksFromFrontmatter(frontmatter, resolvedName),
    executionContext: frontmatter.context === 'fork' ? 'fork' : undefined,
    agent: frontmatter.agent as string | undefined,
    effort,
    shell: parseShellFrontmatter(frontmatter.shell, resolvedName),
  }
}

// ────────────────────────────────────────────────────────────────────────────
// Criação do objeto Command
// ────────────────────────────────────────────────────────────────────────────

export function createSkillCommand({
  skillName,
  displayName,
  description,
  hasUserSpecifiedDescription,
  markdownContent,
  allowedTools,
  argumentHint,
  argumentNames,
  whenToUse,
  version,
  model,
  disableModelInvocation,
  userInvocable,
  source,
  baseDir,
  loadedFrom,
  hooks,
  executionContext,
  agent,
  paths,
  effort,
  shell,
}: {
  skillName: string
  displayName: string | undefined
  description: string
  hasUserSpecifiedDescription: boolean
  markdownContent: string
  allowedTools: string[]
  argumentHint: string | undefined
  argumentNames: string[]
  whenToUse: string | undefined
  version: string | undefined
  model: string | undefined
  disableModelInvocation: boolean
  userInvocable: boolean
  source: PromptCommand['source']
  baseDir: string | undefined
  loadedFrom: LoadedFrom
  hooks: HooksSettings | undefined
  executionContext: 'inline' | 'fork' | undefined
  agent: string | undefined
  paths: string[] | undefined
  effort: EffortValue | undefined
  shell: FrontmatterShell | undefined
}): Command {
  return {
    type: 'prompt',
    name: skillName,
    description,
    hasUserSpecifiedDescription,
    allowedTools,
    argumentHint,
    argNames: argumentNames.length > 0 ? argumentNames : undefined,
    whenToUse,
    version,
    model,
    disableModelInvocation,
    userInvocable,
    context: executionContext,
    agent,
    effort,
    paths,
    contentLength: markdownContent.length,
    isHidden: !userInvocable,
    progressMessage: 'running',
    userFacingName(): string {
      return displayName || skillName
    },
    source,
    loadedFrom,
    hooks,
    skillRoot: baseDir,
    async getPromptForCommand(args, toolUseContext) {
      let finalContent = baseDir
        ? `Base directory for this skill: ${baseDir}\n\n${markdownContent}`
        : markdownContent

      finalContent = substituteArguments(
        finalContent,
        args,
        true,
        argumentNames,
      )

      if (baseDir) {
        const skillDir =
          process.platform === 'win32' ? baseDir.replace(/\\/g, '/') : baseDir
        finalContent = finalContent.replace(/\$\{CLAUDE_SKILL_DIR\}/g, skillDir)
      }

      finalContent = finalContent.replace(
        /\$\{CLAUDE_SESSION_ID\}/g,
        getSessionId(),
      )

      if (loadedFrom !== 'mcp') {
        finalContent = await executeShellCommandsInPrompt(
          finalContent,
          {
            ...toolUseContext,
            getAppState() {
              const appState = toolUseContext.getAppState()
              return {
                ...appState,
                toolPermissionContext: {
                  ...appState.toolPermissionContext,
                  alwaysAllowRules: {
                    ...appState.toolPermissionContext.alwaysAllowRules,
                    command: allowedTools,
                  },
                },
              }
            },
          },
          `/${skillName}`,
          shell,
        )
      }

      return [{ type: 'text', text: finalContent }]
    },
  } satisfies Command
}

// ────────────────────────────────────────────────────────────────────────────
// Carregamento de skills a partir de diretórios /skills/
// ────────────────────────────────────────────────────────────────────────────

type SkillWithPath = {
  skill: Command
  filePath: string
}

async function loadSkillsFromSkillsDir(
  basePath: string,
  source: SettingSource,
  fs = getFsImplementation(),
): Promise<SkillWithPath[]> {
  let entries
  try {
    entries = await fs.readdir(basePath)
  } catch (e: unknown) {
    if (!isFsInaccessible(e)) logError(e)
    return []
  }

  const results = await Promise.all(
    entries.map(async (entry): Promise<SkillWithPath | null> => {
      try {
        if (!entry.isDirectory() && !entry.isSymbolicLink()) return null

        const skillDirPath = join(basePath, entry.name)
        const skillFilePath = join(skillDirPath, 'SKILL.md')

        let content: string
        try {
          content = await fs.readFile(skillFilePath, { encoding: 'utf-8' })
        } catch (e: unknown) {
          if (!isENOENT(e)) {
            logForDebugging(`[skills] failed to read ${skillFilePath}: ${e}`, {
              level: 'warn',
            })
          }
          return null
        }

        const { frontmatter, content: markdownContent } = parseFrontmatter(
          content,
          skillFilePath,
        )

        const skillName = entry.name
        const parsed = parseSkillFrontmatterFields(
          frontmatter,
          markdownContent,
          skillName,
        )
        const paths = parseSkillPaths(frontmatter)

        return {
          skill: createSkillCommand({
            ...parsed,
            skillName,
            markdownContent,
            source,
            baseDir: skillDirPath,
            loadedFrom: 'skills',
            paths,
          }),
          filePath: skillFilePath,
        }
      } catch (error) {
        logError(error)
        return null
      }
    }),
  )

  return results.filter((r): r is SkillWithPath => r !== null)
}

// ────────────────────────────────────────────────────────────────────────────
// Carregamento de skills legadas (diretório /commands/)
// ────────────────────────────────────────────────────────────────────────────

function isSkillFile(filePath: string): boolean {
  return /^skill\.md$/i.test(basename(filePath))
}

function transformSkillFiles(files: MarkdownFile[]): MarkdownFile[] {
  const filesByDir = new Map<string, MarkdownFile[]>()

  for (const file of files) {
    const dir = dirname(file.filePath)
    const dirFiles = filesByDir.get(dir) ?? []
    dirFiles.push(file)
    filesByDir.set(dir, dirFiles)
  }

  const result: MarkdownFile[] = []
  for (const [dir, dirFiles] of filesByDir) {
    const skillFiles = dirFiles.filter(f => isSkillFile(f.filePath))
    if (skillFiles.length > 0) {
      const skillFile = skillFiles[0]!
      if (skillFiles.length > 1) {
        logForDebugging(
          `Multiple skill files found in ${dir}, using ${basename(skillFile.filePath)}`,
        )
      }
      result.push(skillFile)
    } else {
      result.push(...dirFiles)
    }
  }
  return result
}

function buildNamespace(targetDir: string, baseDir: string): string {
  const normalizedBaseDir = baseDir.endsWith(pathSep)
    ? baseDir.slice(0, -1)
    : baseDir
  if (targetDir === normalizedBaseDir) return ''
  const relativePath = targetDir.slice(normalizedBaseDir.length + 1)
  return relativePath ? relativePath.split(pathSep).join(':') : ''
}

function getSkillCommandName(filePath: string, baseDir: string): string {
  const skillDirectory = dirname(filePath)
  const parentOfSkillDir = dirname(skillDirectory)
  const commandBaseName = basename(skillDirectory)
  const namespace = buildNamespace(parentOfSkillDir, baseDir)
  return namespace ? `${namespace}:${commandBaseName}` : commandBaseName
}

function getRegularCommandName(filePath: string, baseDir: string): string {
  const fileName = basename(filePath)
  const fileDirectory = dirname(filePath)
  const commandBaseName = fileName.replace(/\.md$/, '')
  const namespace = buildNamespace(fileDirectory, baseDir)
  return namespace ? `${namespace}:${commandBaseName}` : commandBaseName
}

function getCommandName(file: MarkdownFile): string {
  const isSkill = isSkillFile(file.filePath)
  return isSkill
    ? getSkillCommandName(file.filePath, file.baseDir)
    : getRegularCommandName(file.filePath, file.baseDir)
}

async function loadSkillsFromCommandsDir(
  cwd: string,
  fs = getFsImplementation(),
): Promise<SkillWithPath[]> {
  try {
    const markdownFiles = await loadMarkdownFilesForSubdir('commands', cwd, fs)
    const processedFiles = transformSkillFiles(markdownFiles)

    const skills: SkillWithPath[] = []

    for (const {
      baseDir,
      filePath,
      frontmatter,
      content,
      source,
    } of processedFiles) {
      try {
        const isSkillFormat = isSkillFile(filePath)
        const skillDirectory = isSkillFormat ? dirname(filePath) : undefined
        const cmdName = getCommandName({
          baseDir,
          filePath,
          frontmatter,
          content,
          source,
        })

        const parsed = parseSkillFrontmatterFields(
          frontmatter,
          content,
          cmdName,
          'Custom command',
        )

        skills.push({
          skill: createSkillCommand({
            ...parsed,
            skillName: cmdName,
            displayName: undefined,
            markdownContent: content,
            source,
            baseDir: skillDirectory,
            loadedFrom: 'commands_DEPRECATED',
            paths: undefined,
          }),
          filePath,
        })
      } catch (error) {
        logError(error)
      }
    }

    return skills
  } catch (error) {
    logError(error)
    return []
  }
}

// ────────────────────────────────────────────────────────────────────────────
// Skills condicionais (paths) – indexação e ativação
// ────────────────────────────────────────────────────────────────────────────

/**
 * Mapa de skills condicionais ainda não ativadas (name → Command).
 */
const conditionalSkills = new Map<string, Command>()

/**
 * Conjunto de nomes de skills já ativadas (para evitar reativação).
 */
const activatedConditionalSkillNames = new Set<string>()

/**
 * Índice de padrões para skills condicionais: pattern → nomes de skills.
 * Construído durante o carregamento para busca eficiente.
 */
const conditionalPatternIndex = new Map<string, Set<string>>()

function rebuildConditionalIndex(): void {
  conditionalPatternIndex.clear()
  for (const [name, skill] of conditionalSkills) {
    if (skill.type !== 'prompt' || !skill.paths) continue
    for (const pattern of skill.paths) {
      if (!conditionalPatternIndex.has(pattern)) {
        conditionalPatternIndex.set(pattern, new Set())
      }
      conditionalPatternIndex.get(pattern)!.add(name)
    }
  }
}

/**
 * Ativa skills condicionais cujos padrões correspondem a um determinado caminho.
 */
export function activateConditionalSkillsForPaths(
  filePaths: string[],
  cwd: string,
): string[] {
  if (conditionalSkills.size === 0) return []

  const activated: string[] = []

  // Pré‑compila um objeto ignore para cada pattern único? Muitos patterns.
  // Para performance, usamos um único ignore com todos os patterns e depois
  // verificamos quais skills correspondem. Isso requer mapear de pattern para skill.
  // Vamos fazer um único ignore e depois, para cada pattern que ignora, mapear para skills.

  // Construir lista de todos os patterns
  const allPatterns = Array.from(conditionalPatternIndex.keys())
  if (allPatterns.length === 0) return []

  const skillIgnore = ignore().add(allPatterns)

  for (const filePath of filePaths) {
    const relativePath = isAbsolute(filePath)
      ? relative(cwd, filePath)
      : filePath
    if (
      !relativePath ||
      relativePath.startsWith('..') ||
      isAbsolute(relativePath)
    ) {
      continue
    }

    // Quais patterns ignoram esse arquivo?
    const matchedPatterns = allPatterns.filter(p => skillIgnore.ignores(relativePath))
    if (matchedPatterns.length === 0) continue

    // Para cada pattern, obter as skills associadas
    for (const pattern of matchedPatterns) {
      const skillNames = conditionalPatternIndex.get(pattern)
      if (!skillNames) continue
      for (const name of skillNames) {
        const skill = conditionalSkills.get(name)
        if (!skill || skill.type !== 'prompt') continue
        // Ativa (move para dynamicSkills)
        dynamicSkills.set(name, skill)
        conditionalSkills.delete(name)
        activatedConditionalSkillNames.add(name)
        activated.push(name)
        logForDebugging(
          `[skills] Activated conditional skill '${name}' (matched path: ${relativePath})`,
        )
      }
    }
  }

  if (activated.length > 0) {
    logEvent('tengu_dynamic_skills_changed', {
      source:
        'conditional_paths' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
      previousCount: dynamicSkills.size - activated.length,
      newCount: dynamicSkills.size,
      addedCount: activated.length,
      directoryCount: 0,
    })
    // Notifica listeners (skillsLoaded) – ver abaixo
    skillsLoaded.emit()
  }

  return activated
}

// ────────────────────────────────────────────────────────────────────────────
// Skills dinâmicas (descobertas durante a sessão)
// ────────────────────────────────────────────────────────────────────────────

/**
 * Diretórios de skills já verificados (para não repetir stat).
 */
const dynamicSkillDirs = new Set<string>()

/**
 * Skills descobertas dinamicamente (name → Command).
 */
const dynamicSkills = new Map<string, Command>()

// Sinal emitido quando skills dinâmicas são carregadas
const skillsLoaded = createSignal()

export function onDynamicSkillsLoaded(callback: () => void): () => void {
  return skillsLoaded.subscribe(() => {
    try {
      callback()
    } catch (error) {
      logError(error)
    }
  })
}

/**
 * Descobre diretórios .claude/skills a partir de caminhos de arquivos.
 */
export async function discoverSkillDirsForPaths(
  filePaths: string[],
  cwd: string,
  fs = getFsImplementation(),
): Promise<string[]> {
  const resolvedCwd = cwd.endsWith(pathSep) ? cwd.slice(0, -1) : cwd
  const newDirs: string[] = []

  for (const filePath of filePaths) {
    let currentDir = dirname(filePath)

    while (currentDir.startsWith(resolvedCwd + pathSep)) {
      const skillDir = join(currentDir, '.claude', 'skills')

      if (!dynamicSkillDirs.has(skillDir)) {
        dynamicSkillDirs.add(skillDir)
        try {
          await fs.stat(skillDir)
          if (await isPathGitignored(currentDir, resolvedCwd)) {
            logForDebugging(`[skills] Skipped gitignored skills dir: ${skillDir}`)
            continue
          }
          newDirs.push(skillDir)
        } catch {
          // diretório não existe – já marcado como verificado
        }
      }

      const parent = dirname(currentDir)
      if (parent === currentDir) break
      currentDir = parent
    }
  }

  // Ordena por profundidade decrescente
  return newDirs.sort(
    (a, b) => b.split(pathSep).length - a.split(pathSep).length,
  )
}

/**
 * Carrega skills a partir de diretórios e as adiciona ao mapa dinâmico.
 */
export async function addSkillDirectories(
  dirs: string[],
  fs = getFsImplementation(),
): Promise<void> {
  if (
    !isSettingSourceEnabled('projectSettings') ||
    isRestrictedToPluginOnly('skills')
  ) {
    logForDebugging(
      '[skills] Dynamic skill discovery skipped: projectSettings disabled or plugin-only policy',
    )
    return
  }
  if (dirs.length === 0) return

  const previousSkillNames = new Set(dynamicSkills.keys())
  const loadedSkills = await Promise.all(
    dirs.map(dir => loadSkillsFromSkillsDir(dir, 'projectSettings', fs)),
  )

  // Processa na ordem inversa (do mais raso para o mais profundo) para que os mais profundos sobrescrevam
  for (let i = loadedSkills.length - 1; i >= 0; i--) {
    for (const { skill } of loadedSkills[i] ?? []) {
      if (skill.type === 'prompt') {
        dynamicSkills.set(skill.name, skill)
      }
    }
  }

  const newSkillCount = loadedSkills.flat().length
  if (newSkillCount > 0) {
    const addedSkills = [...dynamicSkills.keys()].filter(
      n => !previousSkillNames.has(n),
    )
    logForDebugging(
      `[skills] Dynamically discovered ${newSkillCount} skills from ${dirs.length} directories`,
    )
    if (addedSkills.length > 0) {
      logEvent('tengu_dynamic_skills_changed', {
        source:
          'file_operation' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS,
        previousCount: previousSkillNames.size,
        newCount: dynamicSkills.size,
        addedCount: addedSkills.length,
        directoryCount: dirs.length,
      })
    }
  }

  skillsLoaded.emit()
}

export function getDynamicSkills(): Command[] {
  return Array.from(dynamicSkills.values())
}

// ────────────────────────────────────────────────────────────────────────────
// Carregamento principal (skills iniciais)
// ────────────────────────────────────────────────────────────────────────────

export const getSkillDirCommands = memoize(
  async (cwd: string): Promise<Command[]> => {
    const userSkillsDir = join(getClaudeConfigHomeDir(), 'skills')
    const managedSkillsDir = join(getManagedFilePath(), '.claude', 'skills')
    const projectSkillsDirs = getProjectDirsUpToHome('skills', cwd)

    logForDebugging(
      `Loading skills from: managed=${managedSkillsDir}, user=${userSkillsDir}, project=[${projectSkillsDirs.join(', ')}]`,
    )

    const additionalDirs = getAdditionalDirectoriesForClaudeMd()
    const skillsLocked = isRestrictedToPluginOnly('skills')
    const projectSettingsEnabled =
      isSettingSourceEnabled('projectSettings') && !skillsLocked

    if (isBareMode()) {
      if (additionalDirs.length === 0 || !projectSettingsEnabled) {
        logForDebugging(
          `[bare] Skipping skill dir discovery (${additionalDirs.length === 0 ? 'no --add-dir' : 'projectSettings disabled or skillsLocked'})`,
        )
        return []
      }
      const additionalSkillsNested = await Promise.all(
        additionalDirs.map(dir =>
          loadSkillsFromSkillsDir(join(dir, '.claude', 'skills'), 'projectSettings'),
        ),
      )
      return additionalSkillsNested.flat().map(s => s.skill)
    }

    const [managedSkills, userSkills, projectSkillsNested, additionalSkillsNested, legacyCommands] =
      await Promise.all([
        isEnvTruthy(process.env.CLAUDE_CODE_DISABLE_POLICY_SKILLS)
          ? Promise.resolve([])
          : loadSkillsFromSkillsDir(managedSkillsDir, 'policySettings'),
        isSettingSourceEnabled('userSettings') && !skillsLocked
          ? loadSkillsFromSkillsDir(userSkillsDir, 'userSettings')
          : Promise.resolve([]),
        projectSettingsEnabled
          ? Promise.all(
              projectSkillsDirs.map(dir =>
                loadSkillsFromSkillsDir(dir, 'projectSettings'),
              ),
            )
          : Promise.resolve([]),
        projectSettingsEnabled
          ? Promise.all(
              additionalDirs.map(dir =>
                loadSkillsFromSkillsDir(join(dir, '.claude', 'skills'), 'projectSettings'),
              ),
            )
          : Promise.resolve([]),
        skillsLocked ? Promise.resolve([]) : loadSkillsFromCommandsDir(cwd),
      ])

    const allSkillsWithPaths = [
      ...managedSkills,
      ...userSkills,
      ...projectSkillsNested.flat(),
      ...additionalSkillsNested.flat(),
      ...legacyCommands,
    ]

    // Deduplicação por identidade de arquivo
    const fileIds = await Promise.all(
      allSkillsWithPaths.map(({ skill, filePath }) =>
        skill.type === 'prompt' ? getFileIdentity(filePath) : Promise.resolve(null),
      ),
    )

    const seenFileIds = new Map<
      string,
      SettingSource | 'builtin' | 'mcp' | 'plugin' | 'bundled'
    >()
    const unconditionalSkills: Command[] = []
    const newConditionalSkills: Command[] = []

    for (let i = 0; i < allSkillsWithPaths.length; i++) {
      const entry = allSkillsWithPaths[i]
      if (!entry || entry.skill.type !== 'prompt') continue
      const { skill } = entry

      const fileId = fileIds[i]
      if (fileId) {
        const existingSource = seenFileIds.get(fileId)
        if (existingSource !== undefined) {
          logForDebugging(
            `Skipping duplicate skill '${skill.name}' from ${skill.source} (same file already loaded from ${existingSource})`,
          )
          continue
        }
        seenFileIds.set(fileId, skill.source)
      }

      if (
        skill.type === 'prompt' &&
        skill.paths &&
        skill.paths.length > 0 &&
        !activatedConditionalSkillNames.has(skill.name)
      ) {
        newConditionalSkills.push(skill)
      } else {
        unconditionalSkills.push(skill)
      }
    }

    // Armazena skills condicionais e reconstrói índice
    for (const skill of newConditionalSkills) {
      conditionalSkills.set(skill.name, skill)
    }
    rebuildConditionalIndex()

    if (newConditionalSkills.length > 0) {
      logForDebugging(
        `[skills] ${newConditionalSkills.length} conditional skills stored (activated when matching files are touched)`,
      )
    }

    logForDebugging(
      `Loaded ${unconditionalSkills.length} unique skills (${unconditionalSkills.length} unconditional, ${newConditionalSkills.length} conditional, managed: ${managedSkills.length}, user: ${userSkills.length}, project: ${projectSkillsNested.flat().length}, additional: ${additionalSkillsNested.flat().length}, legacy commands: ${legacyCommands.length})`,
    )

    return unconditionalSkills
  },
)

// ────────────────────────────────────────────────────────────────────────────
// Funções de limpeza e utilitários (para testes)
// ────────────────────────────────────────────────────────────────────────────

export function clearSkillCaches(): void {
  getSkillDirCommands.cache?.clear?.()
  loadMarkdownFilesForSubdir.cache?.clear?.()
  conditionalSkills.clear()
  activatedConditionalSkillNames.clear()
  conditionalPatternIndex.clear()
  dynamicSkills.clear()
  dynamicSkillDirs.clear()
  realpathCache.clear()
}

// Backwards-compatible aliases
export { getSkillDirCommands as getCommandDirCommands }
export { clearSkillCaches as clearCommandCaches }
export { transformSkillFiles }

// Expor funções de teste
export function getConditionalSkillCount(): number {
  return conditionalSkills.size
}

export function clearDynamicSkills(): void {
  dynamicSkillDirs.clear()
  dynamicSkills.clear()
  conditionalSkills.clear()
  activatedConditionalSkillNames.clear()
  conditionalPatternIndex.clear()
}

// ────────────────────────────────────────────────────────────────────────────
// Registro de construtores de MCP skills (evita ciclo de import)
// ────────────────────────────────────────────────────────────────────────────

registerMCPSkillBuilders({
  createSkillCommand,
  parseSkillFrontmatterFields,
})
