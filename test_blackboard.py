#!/usr/bin/env python3
from blackboard_api import BlackboardAPI

def main():
    print("🧪 Probando API de Blackboard...")
    
    api = BlackboardAPI()
    
    # Listar cursos
    print("\n📚 Obteniendo cursos...")
    cursos = api.listar_cursos()
    
    print(f"\n✅ Encontrados {len(cursos)} cursos:\n")
    for curso in cursos:
        print(f"  📖 {curso['nombre']}")
        print(f"     Código: {curso['codigo']}")
        print(f"     Disponible: {'Sí' if curso['disponible'] else 'No'}")
        print(f"     URL: {curso['url']}")
        print()

if __name__ == "__main__":
    main()
