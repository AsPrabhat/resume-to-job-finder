from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
import os
import json
import threading
from src.analyzer import ResumeAnalyzer
from src.scraper import LinkedInScraper
from src.matcher import SemanticMatcher
from src.network import NetworkFinder
from src.job_search import SmartJobFinder, JobSearchService, JobFilters

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'data'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Global state for tracking pipeline progress
pipeline_status = {
    "running": False,
    "phase": "",
    "progress": 0,
    "message": "",
    "results": None,
    "error": None,
    "analysis": None  # Store structured resume analysis
}

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def run_pipeline(resume_path, jobs_per_role, people_per_job, university, job_filters=None):
    # runs everything in background
    global pipeline_status
    
    try:
        pipeline_status["running"] = True
        pipeline_status["error"] = None
        pipeline_status["results"] = None
        pipeline_status["analysis"] = None
        
        # Phase 1: Parse resume
        pipeline_status["phase"] = "Parsing Resume"
        pipeline_status["progress"] = 5
        pipeline_status["message"] = "Extracting text from resume..."
        
        analyzer = ResumeAnalyzer()
        resume_text = analyzer.extract_text(resume_path)
        
        if not resume_text:
            raise Exception("Could not extract text from resume PDF")
        
        pipeline_status["progress"] = 10
        pipeline_status["message"] = "Parsing resume into structured format..."
        
        # parse into json
        parsed_resume = analyzer.parse_resume_structured(resume_text)
        if not parsed_resume:
            raise Exception("Could not parse resume structure")
        
        pipeline_status["progress"] = 20
        pipeline_status["message"] = f"Found: {parsed_resume.get('personal', {}).get('name', 'Candidate')}"
        
        # get role suggestions
        pipeline_status["phase"] = "Analyzing Career Fit"
        pipeline_status["progress"] = 25
        pipeline_status["message"] = "Analyzing skills and experience for role matching..."
        
        suggested_roles_json = analyzer.get_suggested_roles(parsed_data=parsed_resume, n=3)
        
        pipeline_status["progress"] = 35
        pipeline_status["message"] = "Generating career insights..."
        
        # Get career insights
        career_insights = analyzer.get_career_insights(parsed_data=parsed_resume)
        
        # Store full analysis
        pipeline_status["analysis"] = {
            "parsed_resume": parsed_resume,
            "suggested_roles": suggested_roles_json,
            "career_insights": career_insights
        }
        
        # Save analysis to file
        with open("data/analysis_result.json", "w", encoding='utf-8') as f:
            json.dump(pipeline_status["analysis"], f, indent=2)
        
        role_names = [item['role'] for item in suggested_roles_json]
        pipeline_status["progress"] = 40
        pipeline_status["message"] = f"Identified roles: {', '.join(role_names)}"
        
        # Phase 2: Search Jobs using Smart Job Finder
        pipeline_status["phase"] = "Searching Jobs"
        pipeline_status["progress"] = 45
        pipeline_status["message"] = "Searching for job listings with smart filters..."
        
        # Try the new LinkedIn Jobs API first
        job_service = JobSearchService()
        all_jobs = []
        
        if job_service.is_available:
            pipeline_status["message"] = "Using LinkedIn Jobs API with advanced filters..."
            
            # Use SmartJobFinder for intelligent search
            finder = SmartJobFinder(parsed_resume, suggested_roles_json)
            
            user_preferences = job_filters or {}
            user_preferences["limit_per_role"] = jobs_per_role
            
            all_jobs = finder.find_jobs(user_preferences)
            
            # Transform to match expected format
            for job in all_jobs:
                job["search_role"] = job.get("search_keyword", role_names[0])
                job["description"] = f"{job.get('title', '')} at {job.get('company', '')}"
                job["link"] = job.get("link", job.get("jobUrl", ""))
                
            pipeline_status["progress"] = 60
            pipeline_status["message"] = f"Found {len(all_jobs)} jobs via LinkedIn API"
        else:
            # Fallback to original scraper
            pipeline_status["message"] = "Job API not available. Using web scraper..."
            scraper = LinkedInScraper()
            
            for i, role in enumerate(role_names):
                pipeline_status["message"] = f"Scraping jobs for: {role}"
                jobs = scraper.scrape_jobs(role, k=jobs_per_role)
                all_jobs.extend(jobs)
                pipeline_status["progress"] = 45 + ((i + 1) / len(role_names)) * 15
            
            pipeline_status["progress"] = 60
            pipeline_status["message"] = f"Found {len(all_jobs)} jobs"
        
        # Phase 3: Semantic Matching
        pipeline_status["phase"] = "Matching Jobs"
        pipeline_status["progress"] = 65
        pipeline_status["message"] = "Calculating semantic similarity scores..."
        
        matcher = SemanticMatcher()
        scored_jobs = matcher.score_jobs(all_jobs, role_names)
        
        pipeline_status["progress"] = 75
        pipeline_status["message"] = "Jobs scored successfully"
        
        # Phase 4: Find Connections (Multi-Tier Search)
        pipeline_status["phase"] = "Finding Connections"
        pipeline_status["progress"] = 80
        pipeline_status["message"] = f"Searching for {university} alumni (Priority: IITH → All IITs → Employees)..."
        
        # Extract skills from parsed resume for better matching
        resume_skills = []
        if parsed_resume and 'skills' in parsed_resume:
            skills_data = parsed_resume['skills']
            if isinstance(skills_data, dict):
                for category_skills in skills_data.values():
                    if isinstance(category_skills, list):
                        resume_skills.extend(category_skills)
            elif isinstance(skills_data, list):
                resume_skills = skills_data
        
        networker = NetworkFinder(primary_university=university)
        results_db = []
        
        # Track tier statistics across all jobs
        total_tier_stats = {"tier_1": 0, "tier_2": 0, "tier_3": 0, "tier_4": 0}
        
        for i, job in enumerate(scored_jobs):
            job_title = job.get('title', job.get('position', ''))
            pipeline_status["message"] = f"Finding connections at {job['company']} for {job_title}..."
            
            # Use the enhanced tiered search
            result = networker.find_connections_tiered(
                company=job['company'],
                target_count=people_per_job,
                job_title=job_title,
                job_skills=resume_skills[:10],  # Top 10 skills
                include_company_employees=True
            )
            
            connections = result["connections"]
            tier_stats = result["tier_stats"]
            
            # Update total tier stats
            total_tier_stats["tier_1"] += tier_stats.get("tier_1_count", 0)
            total_tier_stats["tier_2"] += tier_stats.get("tier_2_count", 0)
            total_tier_stats["tier_3"] += tier_stats.get("tier_3_count", 0)
            total_tier_stats["tier_4"] += tier_stats.get("tier_4_count", 0)
            
            job['connections'] = connections
            job['connection_tier_stats'] = tier_stats
            results_db.append(job)
            pipeline_status["progress"] = 80 + ((i + 1) / len(scored_jobs)) * 15
        
        # Phase 5: Save Results
        pipeline_status["phase"] = "Saving Results"
        pipeline_status["progress"] = 95
        pipeline_status["message"] = "Writing results to file..."
        
        output_path = "data/final_results.json"
        with open(output_path, "w", encoding='utf-8') as f:
            json.dump(results_db, f, indent=4)
        
        # Create connection summary
        conn_summary = (f"Found {len(results_db)} jobs with connections! "
                       f"({total_tier_stats['tier_1']} IITH alumni, "
                       f"{total_tier_stats['tier_2']} IIT alumni, "
                       f"{total_tier_stats['tier_3']} skilled employees, "
                       f"{total_tier_stats['tier_4']} other employees)")
        
        pipeline_status["progress"] = 100
        pipeline_status["phase"] = "Complete"
        pipeline_status["message"] = conn_summary
        pipeline_status["results"] = results_db
        pipeline_status["tier_stats"] = total_tier_stats
        
    except Exception as e:
        pipeline_status["error"] = str(e)
        pipeline_status["phase"] = "Error"
        pipeline_status["message"] = f"Pipeline failed: {str(e)}"
    
    finally:
        pipeline_status["running"] = False


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_resume():
    # handle file upload and start processing
    global pipeline_status
    
    if pipeline_status["running"]:
        return jsonify({"error": "Pipeline is already running"}), 400
    
    if 'resume' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['resume']
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are allowed"}), 400
    
    # Save the uploaded file
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'resume.pdf')
    file.save(filepath)
    
    # Get configuration from form
    jobs_per_role = int(request.form.get('jobs_per_role', 3))
    people_per_job = int(request.form.get('people_per_job', 2))
    university = request.form.get('university', 'IIT Hyderabad')
    
    # Get job search filter options
    job_filters = {
        "location": request.form.get('location', ''),
        "experience_level": request.form.get('experience_level', ''),
        "job_type": request.form.get('job_type', ''),
        "remote_filter": request.form.get('remote_filter', ''),
        "date_posted": request.form.get('date_posted', ''),
        "salary_range": request.form.get('salary_range', '')
    }
    
    # Clean empty values
    job_filters = {k: v for k, v in job_filters.items() if v}
    
    # Start pipeline in background thread
    thread = threading.Thread(
        target=run_pipeline,
        args=(filepath, jobs_per_role, people_per_job, university, job_filters)
    )
    thread.start()
    
    return jsonify({"status": "started"})


@app.route('/status')
def get_status():
    return jsonify(pipeline_status)


@app.route('/results')
def results():
    results_data = []
    analysis_data = None
    results_path = "data/final_results.json"
    analysis_path = "data/analysis_result.json"
    
    if os.path.exists(results_path):
        with open(results_path, 'r', encoding='utf-8') as f:
            results_data = json.load(f)
    
    if os.path.exists(analysis_path):
        with open(analysis_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
    
    return render_template('results.html', results=results_data, analysis=analysis_data)


@app.route('/profile')
def profile():
    analysis_data = None
    analysis_path = "data/analysis_result.json"
    
    if os.path.exists(analysis_path):
        with open(analysis_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
    
    return render_template('profile.html', analysis=analysis_data)


@app.route('/api/analysis')
def api_analysis():
    analysis_path = "data/analysis_result.json"
    
    if os.path.exists(analysis_path):
        with open(analysis_path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    
    return jsonify({})


@app.route('/api/results')
def api_results():
    results_path = "data/final_results.json"
    
    if os.path.exists(results_path):
        with open(results_path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    
    return jsonify([])


if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    print("Starting server at http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
