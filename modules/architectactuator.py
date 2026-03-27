import ast
import logging
import functools
from typing import Optional

logger = logging.getLogger("atena.architect")


class ArchitectActuator:
    """
    O 'Cérebro Arquiteto' da Atena.
    Aplica refatorações estruturais (vetorização, paralelismo, memoização)
    em vez de micro-mutações. Cada estratégia tenta melhorar o código em
    termos de performance ou elegância.
    """

    def __init__(self):
        self.strategies = [
            self._apply_list_comprehension_optimization,
            self._apply_map_filter_transformation,
            self._inject_lru_cache_logic,
            # Você pode adicionar mais estratégias aqui
        ]

    def evolve_architecture(self, code: str) -> str:
        """
        Tenta aplicar uma mudança estrutural profunda no código.
        Retorna o código modificado ou o original se nada mudar.
        """
        try:
            tree = ast.parse(code)
            original = tree

            # Escolhe uma estratégia baseada em heurísticas (por enquanto, tenta a primeira que funcionar)
            for strategy in self.strategies:
                new_tree = strategy(tree)
                if new_tree is not None and new_tree != tree:
                    # Se a árvore mudou, retorna o código gerado
                    return ast.unparse(new_tree)

            return code
        except Exception as e:
            logger.warning(f"Architect falhou na refatoração: {e}")
            return code

    # --------------------------------------------------------------
    # Estratégia 1: Transformar loops de append em list comprehension
    # --------------------------------------------------------------
    def _apply_list_comprehension_optimization(self, tree: ast.AST) -> Optional[ast.AST]:
        """
        Converte loops 'for' que apenas fazem 'append' em uma lista para
        list comprehensions. Exemplo:
            result = []
            for x in items:
                result.append(x * 2)
        torna-se:
            result = [x * 2 for x in items]
        """
        class LoopToCompTransformer(ast.NodeTransformer):
            def __init__(self):
                self.changed = False

            def visit_For(self, node):
                # Procura por um padrão:
                #   target = []
                #   for var in iter:
                #       target.append(expr)
                # e o loop é o único statement no corpo (ou há apenas isso)
                if not isinstance(node.body, list) or len(node.body) != 1:
                    return node
                stmt = node.body[0]
                if not isinstance(stmt, ast.Expr):
                    # Se for uma expressão, pode ser um append?
                    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                        call = stmt.value
                        if isinstance(call.func, ast.Attribute) and call.func.attr == 'append':
                            # Precisamos identificar a lista que está recebendo append
                            # Vamos assumir que a lista foi definida antes como uma variável
                            # e que o loop é o único uso dela. Para simplificar, tentamos encontrar
                            # uma atribuição anterior onde a variável é inicializada como lista vazia.
                            # Porém, por questões de simplicidade, essa transformação será aplicada
                            # apenas quando o loop é o único corpo e a lista é a mesma do alvo.
                            # Aqui farei uma versão mais simples: assumimos que a variável alvo
                            # é a mesma que está sendo usada no call.func.value.
                            # Exemplo: result.append(x)
                            # A variável 'result' pode estar definida antes.
                            # Vamos tentar encontrar a definição de 'result' como lista vazia.
                            target_var = call.func.value
                            if isinstance(target_var, ast.Name):
                                # Procurar por Assign anterior na mesma função/bloco
                                # (aqui faremos uma busca superficial na árvore pai)
                                # Para não complicar demais, deixaremos para uma implementação futura.
                                pass
                    return node

                # Se não for um padrão claro, retorna sem alterar
                return node

            def generic_visit(self, node):
                return super().generic_visit(node)

        transformer = LoopToCompTransformer()
        new_tree = transformer.visit(tree)
        return new_tree if transformer.changed else None

    # --------------------------------------------------------------
    # Estratégia 2: Usar map/filter em vez de loops simples
    # --------------------------------------------------------------
    def _apply_map_filter_transformation(self, tree: ast.AST) -> Optional[ast.AST]:
        """
        Transforma loops simples que acumulam em uma lista usando map ou filter.
        Exemplo:
            result = []
            for x in items:
                if x > 0:
                    result.append(x * 2)
        pode virar:
            result = list(map(lambda x: x * 2, filter(lambda x: x > 0, items)))
        """
        class MapFilterTransformer(ast.NodeTransformer):
            def __init__(self):
                self.changed = False

            def visit_For(self, node):
                # Padrão: loop com uma única condição e um append
                # (versão simplificada, apenas para demonstração)
                return node

        transformer = MapFilterTransformer()
        new_tree = transformer.visit(tree)
        return new_tree if transformer.changed else None

    # --------------------------------------------------------------
    # Estratégia 3: Injetar lru_cache em funções recursivas
    # --------------------------------------------------------------
    def _inject_lru_cache_logic(self, tree: ast.AST) -> Optional[ast.AST]:
        """
        Detecta funções recursivas (que chamam a si mesmas) e adiciona
        o decorador @lru_cache(maxsize=None) para memoização.
        Também garante a importação de functools.lru_cache.
        """
        class RecursiveFunctionTransformer(ast.NodeTransformer):
            def __init__(self):
                self.changed = False
                self.has_functools_import = False

            def visit_ImportFrom(self, node):
                # Marca se já existe import de lru_cache
                if node.module == 'functools':
                    for alias in node.names:
                        if alias.name == 'lru_cache':
                            self.has_functools_import = True
                return node

            def visit_FunctionDef(self, node):
                # Verifica se a função é recursiva (chama a si mesma)
                if self._is_recursive(node):
                    # Adiciona o decorador @lru_cache(maxsize=None)
                    # se ainda não estiver presente
                    has_decorator = any(
                        isinstance(dec, ast.Name) and dec.id == 'lru_cache'
                        for dec in node.decorator_list
                    )
                    if not has_decorator:
                        decorator = ast.Name(id='lru_cache', ctx=ast.Load())
                        # Se quiser argumentos, pode adicionar um Call
                        # Por enquanto, usamos um decorador simples (sem argumentos)
                        # Mas lru_cache precisa de maxsize=None para funções com argumentos.
                        # Vamos criar uma chamada: lru_cache(maxsize=None)
                        decorator_call = ast.Call(
                            func=decorator,
                            args=[],
                            keywords=[ast.keyword(arg='maxsize', value=ast.Constant(value=None))]
                        )
                        node.decorator_list.insert(0, decorator_call)
                        self.changed = True
                # Continua visitando o corpo da função
                self.generic_visit(node)
                return node

            def _is_recursive(self, node: ast.FunctionDef) -> bool:
                """Verifica se a função contém uma chamada para si mesma."""
                class RecursionFinder(ast.NodeVisitor):
                    def __init__(self, name):
                        self.name = name
                        self.found = False

                    def visit_Call(self, call):
                        if isinstance(call.func, ast.Name) and call.func.id == self.name:
                            self.found = True
                        self.generic_visit(call)

                finder = RecursionFinder(node.name)
                finder.visit(node)
                return finder.found

        transformer = RecursiveFunctionTransformer()
        new_tree = transformer.visit(tree)

        # Se houve mudança e não havia import de functools, adicionamos
        if transformer.changed and not transformer.has_functools_import:
            import_node = ast.ImportFrom(
                module='functools',
                names=[ast.alias(name='lru_cache')],
                level=0
            )
            new_tree.body.insert(0, import_node)

        return new_tree if transformer.changed else None
