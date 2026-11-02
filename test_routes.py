from app.main import app

for route in app.routes:
    if hasattr(route, "methods"):
        print(f"{list(route.methods)} {route.path} -> {route.name}")
