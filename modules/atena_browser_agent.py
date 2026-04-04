import logging
import asyncio
from playwright.async_api import async_playwright, Page, Browser
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class AtenaBrowserAgent:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.context: Optional[Any] = None # BrowserContext

    async def launch(self, headless: bool = True):
        """Inicia o navegador Chromium."""
        logger.info(f"Lançando navegador (headless={headless})...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)
        self.context = await self.browser.new_context(ignore_https_errors=True)
        self.page = await self.context.new_page()
        logger.info("Navegador iniciado com sucesso.")

    async def navigate(self, url: str) -> bool:
        """Navega para uma URL específica."""
        if not self.page:
            logger.error("Navegador não iniciado. Chame launch() primeiro.")
            return False
        try:
            logger.info(f"Navegando para: {url}")
            await self.page.goto(url, wait_until="domcontentloaded")
            logger.info(f"Navegação para {url} concluída.")
            return True
        except Exception as e:
            logger.error(f"Erro ao navegar para {url}: {e}")
            return False

    async def get_page_content(self) -> str:
        """Retorna o conteúdo HTML da página atual."""
        if not self.page:
            return ""
        return await self.page.content()

    async def get_text_content(self) -> str:
        """Retorna todo o texto visível da página atual."""
        if not self.page:
            return ""
        return await self.page.locator("body").text_content()

    async def take_screenshot(self, path: str = "screenshot.png") -> bool:
        """Tira um screenshot da página atual."""
        if not self.page:
            return False
        try:
            await self.page.screenshot(path=path)
            logger.info(f"Screenshot salvo em: {path}")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar screenshot em {path}: {e}")
            return False

    async def click_element(self, selector: str) -> bool:
        """Clica em um elemento usando um seletor CSS."""
        if not self.page:
            return False
        try:
            logger.info(f"Clicando no elemento: {selector}")
            await self.page.click(selector)
            logger.info(f"Elemento {selector} clicado.")
            return True
        except Exception as e:
            logger.error(f"Erro ao clicar em {selector}: {e}")
            return False

    async def type_text(self, selector: str, text: str) -> bool:
        """Digita texto em um campo usando um seletor CSS."""
        if not self.page:
            return False
        try:
            logger.info(f"Digitando \'{text}\' no elemento: {selector}")
            await self.page.fill(selector, text)
            logger.info(f"Texto digitado em {selector}.")
            return True
        except Exception as e:
            logger.error(f"Erro ao digitar em {selector}: {e}")
            return False

    async def close(self):
        """Fecha o navegador."""
        if self.browser:
            await self.browser.close()
            logger.info("Navegador fechado.")
        if self.playwright:
            await self.playwright.stop()
            logger.info("Playwright parado.")

# Exemplo de uso (para testes)
async def main_demo():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    browser_agent = AtenaBrowserAgent()
    try:
        await browser_agent.launch(headless=True)
        await browser_agent.navigate("https://github.com/AtenaAuto/ATENA-")
        await browser_agent.take_screenshot("github_atena.png")
        
        print("\n--- Conteúdo da Página (trecho) ---")
        text_content = await browser_agent.get_text_content()
        print(text_content[:500]) # Imprime os primeiros 500 caracteres

        # Exemplo de busca (se houver um campo de busca visível)
        # await browser_agent.type_text("input[name=\'q\']", "AtenaAI")
        # await browser_agent.page.press("input[name=\'q\']", "Enter")
        # await browser_agent.page.wait_for_load_state("networkidle")
        # await browser_agent.take_screenshot("github_search_results.png")

    except Exception as e:
        logger.error(f"Erro na demonstração do Browser Agent: {e}")
    finally:
        await browser_agent.close()

if __name__ == "__main__":
    asyncio.run(main_demo())
