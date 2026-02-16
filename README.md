> *🌱 Sortify — AI-Powered Waste Sorting Game https://sortifywebsiteapp.base44.app

Sortify is a gamified web application that uses AI-powered image recognition to help users correctly sort waste into Recycle, Compost, or Landfill bins.
By turning sustainability into a game, Sortify educates users while encouraging real-world environmental impact.

🎮 What the Game Offers

📸 AI Waste Scanning
Users upload or capture an image of an item
A pretrained AI model analyzes the object
The system predicts the correct bin:
♻️ Recycle
🌱 Compost
🗑️ Landfill
A confidence score (%) and human-readable explanation are returned

🏆 Points & Leaderboard System
+1 point awarded per successful scan
Real-time leaderboard ranks users globally
Encourages consistency and friendly competition

🗺️ Smart Bin Locator
Uses location data to show nearby disposal bins
Supports recycling, compost, and waste bins
Integrated directly into the app for convenience

👤 User Profiles
Secure login system
View total points, scan history, and rank
Tracks environmental impact over time

🧠 Educational Impact
Explains why an item belongs in a specific bin
Helps users learn sustainable habits, not just score points

🛒 Additional Products & Upgrades (Planned)
These are optional enhancements designed for future expansion

💎 Sortify+ (Premium)
Detailed scan history analytics
Environmental impact breakdown (CO₂ saved, waste diverted)
Advanced AI confidence explanations

🏫 Institutional Edition
Custom leaderboards for schools or organizations
Admin dashboards
CSV data export for sustainability reporting

🧺 Smart Bin Integration (Hardware Add-on)
Ultrasonic bin fill-level tracking
Real-time “bin full” status
Optimized pickup routing (future scope)

🧩 System Architecture Overview
Frontend (React + Vite)
        ↓ API Requests
gi
        ↓
SQLite Database
        ↓
AI Model + External APIs

🛠️ Technology Stack

Frontend
React (TypeScript)
Vite (fast development & builds)
Tailwind CSS
React Router (page navigation)
Backend
FastAPI (Python)
Uvicorn (ASGI server)
Pydantic (data validation)
RESTful API design
Database
SQLite
Lightweight

Perfect for hackathons & prototypes
Stores users, scans, points, leaderboard data
AI & APIs

Google Gemini API – object recognition & explanation

Google Maps API – bin location mapping

(Optional fallback: OpenStreetMap)

🔐 Authentication & Security
Token-based authentication
Firebase Auth support (optional / hybrid)
API keys stored securely via environment variables
No secrets committed to GitHub

🔑 Environment Variables
Create a .env file in the backend root:
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_MAPS_API_KEY=your_google_maps_key
DATABASE_URL=sqlite:///sortify.db
⚠️ Never commit .env files to version control

📂 Project Structure (Simplified)
SORTIFY/
├── frontend/
│   ├── src/
│   ├── pages/
│   ├── components/
│   └── vite.config.ts
│
├── backend/
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   └── auth.py
│
├── .venv/
├── package.json
├── SORTIFY_README.md
└── ATTRIBUTIONS.md

**🚀 How to Run the Project
Backend**
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

Backend runs at:
http://127.0.0.1:8000

Frontend
npm install
npm run dev
Frontend runs at:
http://localhost:5173

🧪 API Example
Scan Item
POST /scan
{
  "image_base64": "...",
  "lat": 37.7749,
  "lng": -122.4194
}
Response
{
  "detected_item": "plastic bottle",
  "bin_category": "recycle",
  "confidence": 0.92,
  "explanation": "Plastic bottles made of PET are recyclable",
  "new_user_points": 42
}

🌍 Mission Statement
Sortify exists to make sustainability simple, educational, and rewarding.
By combining AI, gamification, and real-world data, we empower people to make smarter waste decisions every day.
