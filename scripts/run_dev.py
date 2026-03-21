from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.config import get_settings


def main() -> None:
    settings = get_settings()
    print("Use this command to run the API server:")
    print("uvicorn app.main:app --reload")
    print(f"API prefix: {settings.api_prefix}")


if __name__ == "__main__":
    main()
