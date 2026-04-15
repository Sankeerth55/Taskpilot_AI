#!/usr/bin/env python3
"""
TaskPilot AI Backend - Quick Start Script
Cross-platform server startup with configuration checks
"""

import os
import subprocess
import sys
import argparse
from pathlib import Path


def ensure_backend_directory() -> bool:
    """Ensure the process is running from the backend directory."""
    if Path("app/main.py").exists():
        return True

    script_dir = Path(__file__).resolve().parent
    if (script_dir / "app/main.py").exists():
        os.chdir(script_dir)
        print(f"✅ Switched to backend directory: {script_dir}")
        return True

    print("❌ Error: Could not locate backend app/main.py")
    print(f"   Current: {Path.cwd()}")
    print(f"   Script dir: {script_dir}")
    return False


def check_env_file():
    """Check if .env file exists."""
    if not Path(".env").exists():
        print("⚠️  Warning: .env file not found")
        if Path(".env.example").exists():
            print("📝 Creating .env from .env.example...")
            try:
                with open(".env.example", "r", encoding="utf-8") as src:
                    content = src.read()
                with open(".env", "w", encoding="utf-8") as dst:
                    dst.write(content)
                print("✅ Created .env file")
                print("💡 Edit .env to configure your GEMINI_API_KEY")
                return True
            except Exception as e:
                print(f"❌ Failed to create .env: {e}")
                return False
        else:
            print("❌ .env.example not found")
            return False
    else:
        # Check if API key is configured
        with open(".env", "r", encoding="utf-8") as f:
            content = f.read()
            if "GEMINI_API_KEY=" in content and "your_" not in content:
                print("✅ .env file found with API key configured")
            else:
                print("⚠️  .env file found but API key may not be configured")
    return True


def check_dependencies():
    """Check if required dependencies are installed."""
    print("🔍 Checking dependencies...")
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        print("✅ Core dependencies installed")
        return True
    except ImportError:
        print("⚠️  Dependencies not installed")
        print("📦 Installing dependencies...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("✅ Dependencies installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies")
            print("💡 Try manually: pip install -r requirements.txt")
            return False


def verify_configuration() -> None:
    """Run optional Gemini configuration verification."""
    print()
    print("━" * 60)
    print("🔄 Running verification...")
    try:
        result = subprocess.run([sys.executable, "verify_gemini.py"])
        if result.returncode != 0:
            print("⚠️  Verification had issues, server will still start with fallbacks")
    except Exception as e:
        print(f"⚠️  Could not run verification: {e}")
        print("💡 Server can still run with fallback logic")
    print()


def start_server(host: str, port: int, reload_enabled: bool):
    """Start the FastAPI server."""
    print("=" * 60)
    print("  TaskPilot AI Backend - Starting Server")
    print("=" * 60)
    print()
    print("📍 Server will be available at:")
    print(f"   • http://{host}:{port}")
    print(f"   • http://{host}:{port}/docs (API Documentation)")
    print()
    print("💡 Press Ctrl+C to stop the server")
    print()
    print("━" * 60)
    print()
    
    try:
        cmd = [
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", host,
            "--port", str(port)
        ]
        if reload_enabled:
            cmd.append("--reload")

        subprocess.run(cmd)
    except KeyboardInterrupt:
        print()
        print("🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return False
    
    return True


def main():
    """Main startup routine."""
    parser = argparse.ArgumentParser(description="TaskPilot AI backend launcher")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--skip-verify", action="store_true", help="Skip Gemini verification")
    parser.add_argument("--no-reload", action="store_true", help="Disable uvicorn auto-reload")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  TaskPilot AI Backend - Quick Start")
    print("=" * 60)
    print()
    
    # Check environment
    if not ensure_backend_directory():
        sys.exit(1)
    
    # Check .env file
    if not check_env_file():
        print()
        print("⚠️  Continuing without .env; server will use fallbacks where possible")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Optional verification
    if not args.skip_verify:
        verify_configuration()
    
    # Start server
    success = start_server(args.host, args.port, not args.no_reload)
    
    print()
    print("👋 Goodbye!")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print("👋 Startup cancelled by user")
        sys.exit(0)
