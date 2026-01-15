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
- Python 3.10+
- Node.js 18+
- API Keys:
  - [OpenRouter](https://openrouter.ai/) - for resume analysis
  - [Serper](https://serper.dev/) - for finding LinkedIn profiles

### Installation

```bash
# Clone the repo
git clone https://github.com/AsPrabhat/resume-to-job-finder
cd resume-to-job-finder

# Python setup
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Node setup (for job search)
cd scripts
npm install
cd ..
```

### Environment Variables

Create a `.env` file in the root folder:
```
OPENROUTER_API_KEY=your_key_here
SERPER_API_KEY=your_key_here
```

### Running

You need two terminals:

```bash
# Terminal 1 - Start job search service
cd scripts
node job_service.js

# Terminal 2 - Start web app
python app.py
```

Open http://localhost:5000 in your browser.

## Project Structure

```
├── app.py              # Flask web app
├── src/
│   ├── analyzer.py     # Resume parsing & role suggestions
│   ├── matcher.py      # Semantic job matching (sentence transformers)
│   ├── network.py      # Multi-tier connection finder
│   ├── scraper.py      # Backup LinkedIn scraper
│   └── job_search.py   # Job search with filters
├── scripts/
│   └── job_service.js  # Node.js LinkedIn Jobs API service
├── templates/          # HTML templates
├── static/             # CSS styles
└── data/               # Output files (gitignored)
```

## Tech Stack

- **Backend**: Python, Flask
- **Frontend**: HTML, CSS, Bootstrap
- **AI/ML**: OpenRouter API, Sentence Transformers
- **Job Search**: linkedin-jobs-api (Node.js)
- **Profile Search**: Serper API

## Notes

- The connection finder prioritizes IITH alumni, then other IIT alumni, then company employees
- Job matching uses sentence transformers for semantic similarity
- Results are cached to avoid hitting API limits
