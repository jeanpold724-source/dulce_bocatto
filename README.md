# 🍪 Dulce Bocatto SI1

Sistema web académico desarrollado con Django para gestionar usuarios y clientes en un entorno limpio, funcional y escalable.

---

## 🚀 Funcionalidades implementadas

- ✅ Registro de usuarios con email como identificador (CU01)
- ✅ Inicio de sesión personalizado (CU02)
- 🔄 Modelo `User` extendido con campo de teléfono
- 🧱 Estructura lista para integrar modelo `Client` y vistas protegidas
- 🌐 Navegación básica con página principal (`/`), registro (`/register`) y login (`/login`)

---

## 🛠️ Tecnologías utilizadas

- Python 3.12.3
- Django 5.2.6
- SQLite (por defecto, listo para migrar a MySQL)
- HTML + Bootstrap (próximamente)
- Git + GitHub para control de versiones

---

## 📦 Instalación rápida

```bash
git clone https://github.com/alecaballero17/DulceBocattoSI1.git
cd DulceBocattoSI1
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
