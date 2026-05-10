import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


class BlackboardAuth:
    def __init__(self):
        self.BASE_URL = "https://upn.blackboard.com/ultra/course"
        self.cookies_path = Path("blackboard_cookies.json")
    
    def obtener_cookies_selenium(self):
        """Login manual con Selenium y extrae cookies importantes"""
        print("🌐 Abriendo Chrome para login...")
        opciones = Options()
        opciones.add_argument('--no-sandbox')
        opciones.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(options=opciones)
        driver.get(self.BASE_URL)
        
        print("👤 Por favor, inicia sesión manualmente en Chrome")
        print("⏳ Esperando login... Presiona Enter cuando estés en Blackboard")
        input()
        
        # Extraer cookies importantes
        cookies = driver.get_cookies()
        cookies_dict = {}
        for cookie in cookies:
            cookies_dict[cookie['name']] = cookie['value']
        
        # Guardar
        with open(self.cookies_path, 'w') as f:
            json.dump(cookies_dict, f, indent=2)
        
        print(f"✅ Cookies guardadas en {self.cookies_path}")
        driver.quit()
        return cookies_dict
    
    def cargar_cookies(self):
        """Carga cookies del archivo JSON"""
        if not self.cookies_path.exists():
            print("⚠️  No hay cookies guardadas")
            return None
        
        with open(self.cookies_path, 'r') as f:
            return json.load(f)
    
    def cookies_validas(self, cookies):
        """Verifica si las cookies siguen válidas"""
        # Verificar que existan las cookies críticas
        required = ['JSESSIONID', 'BbRouter']
        return all(key in cookies for key in required)
    
    def obtener_cookies(self, forzar_renovar=False):
        """Obtiene cookies válidas (del archivo o renovando)"""
        if not forzar_renovar:
            cookies = self.cargar_cookies()
            if cookies and self.cookies_validas(cookies):
                print("✅ Usando cookies guardadas")
                return cookies
        
        print("🔄 Renovando cookies...")
        return self.obtener_cookies_selenium()
