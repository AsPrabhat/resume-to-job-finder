# Resume Job Finder

A web app that analyzes your resume, finds relevant job listings, and helps you connect with people at those companies.

Built as a project to help job seekers find opportunities and network with potential referrals.

## Features

- **Resume Analysis** - Upload a PDF and get AI-powered skill extraction and role suggestions
- **Job Search** - Automatically searches LinkedIn for jobs matching your profile
- **Smart Matching** - Uses NLP to score how well each job matches your skills
- **Connection Finder** - Finds people at companies who might help with referrals (prioritizes alumni networks)

## How it Works

1. Upload your resume (PDF)
2. AI extracts your skills, experience, and suggests suitable job roles
3. Searches LinkedIn for matching positions
4. For each job, finds people at that company (prioritizes IITH → other IITs → company employees)
5. Shows results with match scores and potential connections

## Setup

### Requirements
- Python 3.10 or higher
- Node.js 18 or higher
- API Keys (free tiers available):
  - [OpenRouter](https://openrouter.ai/) - for resume analysis (sign up and get API key)
  - [Serper](https://serper.dev/) - for finding LinkedIn profiles (2500 free searches)

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/AsPrabhat/resume-to-job-finder
cd resume-to-job-finder
```

**2. Set up Python virtual environment**
```bash
# Create virtual environment
python -m venv .venv

# Activate it (Windows)
.venv\Scripts\activate

# Activate it (Mac/Linux)
source .venv/bin/activate
```

**3. Install Python dependencies**
```bash
pip install -r requirements.txt
```

**4. Install Node.js dependencies**
```bash
cd scripts
npm install
cd ..
```

**5. Create environment file**

Create a file named `.env` in the project root folder with your API keys:
```
OPENROUTER_API_KEY=your_openrouter_key_here
SERPER_API_KEY=your_serper_key_here
```

### Running the App

You need **two terminal windows** running simultaneously:

**Terminal 1 - Start the job search service:**
```bash
cd scripts
node job_service.js
```
You should see: `Job search service running on http://localhost:3001`

**Terminal 2 - Start the Flask web app:**
```bash
python app.py
```
You should see: `Starting server at http://localhost:5000`

**Open your browser** and go to: http://localhost:5000

## Usage

1. Click "Choose File" and select your resume PDF
2. Adjust settings (jobs per role, connections per job, target university)
3. Click "Start Analysis"
4. Wait for the pipeline to complete (takes 1-2 minutes)
5. View your results with job matches and potential connections

## Project Structure

```
├── app.py              # Flask web app (main entry point)
├── requirements.txt    # Python dependencies
├── .env                # API keys (create this yourself)
├── src/
│   ├── analyzer.py     # Resume parsing & role suggestions
│   ├── matcher.py      # Semantic job matching
│   ├── network.py      # Multi-tier connection finder
│   ├── scraper.py      # Backup LinkedIn scraper
│   └── job_search.py   # Job search with filters
├── scripts/
│   ├── job_service.js  # Node.js job search service
│   └── package.json    # Node.js dependencies
├── templates/          # HTML templates
├── static/             # CSS styles
└── data/               # Output files (auto-created)
```

## Tech Stack

- **Backend**: Python 3.10+, Flask
- **Frontend**: HTML, CSS, Bootstrap 5
- **AI/ML**: OpenRouter API (DeepSeek), Sentence Transformers
- **Job Search**: linkedin-jobs-api (Node.js)
- **Profile Search**: Serper.dev API

## Troubleshooting

- **"Module not found" errors**: Make sure virtual environment is activated
- **Job search not working**: Check if Node.js service is running on port 3001
- **No connections found**: Verify your SERPER_API_KEY is correct
- **Resume parsing fails**: Check your OPENROUTER_API_KEY is valid

## Notes

- Connection finder prioritizes: IITH alumni → All IIT alumni → Skilled employees → General employees
- Job matching uses sentence-transformers for semantic similarity scoring
- Results are cached to avoid hitting API rate limits
- Results are cached to avoid hitting API limits
