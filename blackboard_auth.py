import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

from logger import get_logger

log = get_logger(__name__)


class BlackboardAuth:
    def __init__(self):
        self.BASE_URL = "https://upn.blackboard.com/ultra/course"
        self.cookies_path = Path("blackboard_cookies.json")

    def obtener_cookies_selenium(self):
        """Login manual con Selenium y extrae cookies importantes."""
        log.info("🌐 Abriendo Chrome para login...")
        opciones = Options()
        opciones.add_argument('--no-sandbox')
        opciones.add_argument('--disable-dev-shm-usage')

        # try/finally garantiza que driver.quit() se ejecute incluso si
        # hay una excepción en el WebDriverWait, input() o get_cookies().
        # Sin esto, Chrome quedaba zombie consumiendo RAM.
        driver = webdriver.Chrome(options=opciones)
        try:
            driver.get(self.BASE_URL)

            log.info("👤 Inicia sesión manualmente en Chrome.")
            log.info("⏳ Presiona Enter cuando estés en Blackboard...")
            input()

            cookies = driver.get_cookies()
            cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}

            with open(self.cookies_path, 'w') as f:
                json.dump(cookies_dict, f, indent=2)

            log.info("✅ Cookies guardadas en %s", self.cookies_path)
            return cookies_dict
        finally:
            try:
                driver.quit()
            except Exception as error:
                log.warning("driver.quit() falló: %s", error)

    def cargar_cookies(self):
        """Carga cookies del archivo JSON."""
        if not self.cookies_path.exists():
            log.warning("No hay cookies guardadas.")
            return None

        with open(self.cookies_path, 'r') as f:
            return json.load(f)

    def cookies_validas(self, cookies):
        """Verifica si las cookies siguen válidas."""
        required = ['JSESSIONID', 'BbRouter']
        return all(key in cookies for key in required)

    def obtener_cookies(self, forzar_renovar=False):
        """Obtiene cookies válidas (del archivo o renovando)."""
        if not forzar_renovar:
            cookies = self.cargar_cookies()
            if cookies and self.cookies_validas(cookies):
                log.info("✅ Usando cookies guardadas")
                return cookies

        log.info("🔄 Renovando cookies...")
        return self.obtener_cookies_selenium()
