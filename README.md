# Genshin AI Coach 🎮

Personal AI Assistant for Genshin Impact powered by Groq AI

## 🌟 Features

- 💬 **AI Chat** - Ask questions about Genshin Impact (powered by Groq)
- 📊 **Artifact Optimizer** - Find the best artifact combinations
- 🏆 **Character Builds** - Get recommended builds for any character
- 👥 **Team Compositions** - Optimize your team setup
- 🎯 **Spiral Abyss** - Get strategies for Spiral Abyss

## 🚀 Quick Start

### Local Development

```bash
# Clone repo
git clone https://github.com/cb3333099-ux/genshin-ai-coach.git
cd genshin-ai-coach

# Setup backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file
echo "GROQ_API_KEY=your_key_here" > .env

# Run server
python main.py
Backend runs on: http://localhost:8000

Frontend
Open frontend/index.html in browser
Or start a local server: python -m http.server 8001
📋 Setup Requirements
Python 3.9+
Groq API Key (free from https://console.groq.com)
🌐 Live Demo
https://genshin-ai-coach.onrender.com

🛠️ Tech Stack
Backend: FastAPI, Python
Frontend: HTML, CSS, JavaScript
AI: Groq API (Mixtral 8x7B)
Data: Enka.Network API
Hosting: Render
📚 API Endpoints
Chat
POST /api/chat - Chat with AI Coach
Account Data
GET /api/account/{uid} - Fetch player data
Artifact Optimizer
POST /api/optimize - Optimize artifacts
POST /api/recommended-build - Get recommended build
POST /api/optimize-team - Optimize team builds
🤝 Contributing
Feel free to fork and submit PRs!

📄 License
MIT

👨‍💻 Author
[Your Name/cb3333099-ux]

Code

---

### **3. (Optional) Move test file**

Rename `test_groq.py` to `tests/test_groq.py` or delete it if not needed

---

## 🔧 **Steps:**

1. **Go to GitHub repo**
2. **Edit `frontend/script.js`** → Update API URL
3. **Edit `README.md`** → Replace with content above
4. **Commit changes** with message: `"Update API URL and add README"`
5. **Wait 2-3 min** for Render to auto-deploy
6. **Test your app!** 🎉

---

## ✅ **After you're done:**
