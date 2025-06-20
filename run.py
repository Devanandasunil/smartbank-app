from app import create_app
import os

# Required by Glitch
PORT = int(os.environ.get("PORT", 3000))

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=PORT)
