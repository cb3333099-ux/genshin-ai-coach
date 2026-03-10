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
