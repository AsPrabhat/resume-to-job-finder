# job_search.py - searches for jobs using LinkedIn API

import os
import json
import requests
import subprocess
from typing import Optional
from dataclasses import dataclass

# config
JOB_SERVICE_URL = os.getenv("JOB_SERVICE_URL", "http://localhost:3001")


@dataclass
class JobFilters:
    """Filters for job search"""
    location: str = "India"
    experience_level: str = ""  # entry level, associate, mid-senior level, director, executive
    job_type: str = ""  # full time, part time, contract, temporary, internship
    remote_filter: str = ""  # remote, on site, hybrid
    date_posted: str = "past week"  # past month, past week, 24hr
    salary: str = ""  # 40000, 60000, 80000, 100000, 120000
    limit_per_role: int = 5
    sort_by: str = "recent"  # recent, relevant


class QueryBuilder:
    """
    Builds optimized job search queries from parsed resume data
    """
    
    # Experience level mapping
    EXPERIENCE_MAP = {
        (0, 1): "entry level",
        (1, 3): "associate",
        (3, 7): "mid-senior level",
        (7, 12): "director",
        (12, float('inf')): "executive"
    }
    
    def __init__(self, parsed_resume: dict):
        self.resume = parsed_resume
        
    def get_experience_level(self) -> str:
        """Map years of experience to LinkedIn experience level"""
        years = self.resume.get("total_experience_years", 0)
        if years is None:
            years = 0
            
        for (min_years, max_years), level in self.EXPERIENCE_MAP.items():
            if min_years <= years < max_years:
                return level
        return "entry level"
    
    def get_top_skills(self, n: int = 5) -> list:
        """Get top N skills from resume for enhanced search"""
        skills = self.resume.get("skills", {})
        
        # Prioritize technical skills
        all_skills = []
        all_skills.extend(skills.get("technical", [])[:3])
        all_skills.extend(skills.get("frameworks", [])[:2])
        all_skills.extend(skills.get("tools", [])[:2])
        
        return all_skills[:n]
    
    def get_search_keywords(self, roles: list) -> list:
        """
        Build enhanced search keywords combining role + skills
        """
        top_skills = self.get_top_skills(3)
        
        searches = []
        for role in roles:
            if isinstance(role, dict):
                role_name = role.get("role", "")
            else:
                role_name = role
                
            searches.append({
                "keyword": role_name,
                "role": role_name,
                "skills": top_skills
            })
            
        return searches
    
    def build_filters(self, user_preferences: dict = None) -> JobFilters:
        """
        Build job filters from resume + user preferences
        """
        prefs = user_preferences or {}
        
        return JobFilters(
            location=prefs.get("location", "India"),
            experience_level=prefs.get("experience_level") or self.get_experience_level(),
            job_type=prefs.get("job_type", "full time"),
            remote_filter=prefs.get("remote_filter", ""),
            date_posted=prefs.get("date_posted", "past week"),
            salary=prefs.get("salary", ""),
            limit_per_role=prefs.get("limit_per_role", 5),
            sort_by=prefs.get("sort_by", "recent")
        )


class JobSearchService:
    """
    Main job search service that uses LinkedIn Jobs API via Node.js microservice
    """
    
    def __init__(self, service_url: str = JOB_SERVICE_URL):
        self.service_url = service_url
        self.is_available = self._check_service()
        
    def _check_service(self) -> bool:
        """Check if the Node.js job service is running"""
        try:
            response = requests.get(f"{self.service_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def search_jobs(
        self,
        keyword: str,
        filters: JobFilters = None,
        skills: list = None
    ) -> list:
        """
        Search for jobs with a single keyword
        """
        if filters is None:
            filters = JobFilters()
            
        payload = {
            "keyword": keyword,
            "location": filters.location,
            "experienceLevel": filters.experience_level,
            "jobType": filters.job_type,
            "remoteFilter": filters.remote_filter,
            "dateSincePosted": filters.date_posted,
            "salary": filters.salary,
            "limit": filters.limit_per_role,
            "sortBy": filters.sort_by,
            "skills": skills or []
        }
        
        try:
            response = requests.post(
                f"{self.service_url}/search",
                json=payload,
                timeout=30
            )
            data = response.json()
            
            if data.get("success"):
                return data.get("jobs", [])
            else:
                print(f"Search error: {data.get('error')}")
                return []
                
        except Exception as e:
            print(f"Job search failed: {e}")
            return []
    
    def batch_search(
        self,
        searches: list,
        filters: JobFilters = None
    ) -> list:
        """
        Search for multiple keywords/roles at once
        
        Args:
            searches: List of dicts with 'keyword', 'role', 'skills'
            filters: Common filters to apply
        """
        if filters is None:
            filters = JobFilters()
            
        payload = {
            "searches": [
                {
                    "keyword": s.get("keyword", ""),
                    "role": s.get("role", s.get("keyword", "")),
                    "limit": filters.limit_per_role
                }
                for s in searches
            ],
            "commonFilters": {
                "location": filters.location,
                "experienceLevel": filters.experience_level,
                "jobType": filters.job_type,
                "remoteFilter": filters.remote_filter,
                "dateSincePosted": filters.date_posted,
                "sortBy": filters.sort_by,
                "limit": filters.limit_per_role
            }
        }
        
        try:
            response = requests.post(
                f"{self.service_url}/batch-search",
                json=payload,
                timeout=60
            )
            data = response.json()
            
            if data.get("success"):
                jobs = data.get("jobs", [])
                print(f"✅ Found {len(jobs)} jobs from batch search")
                return jobs
            else:
                print(f"Batch search error: {data.get('error')}")
                return []
                
        except Exception as e:
            print(f"Batch job search failed: {e}")
            return []


class SmartJobFinder:
    """
    High-level interface that combines resume analysis with job search
    """
    
    def __init__(self, parsed_resume: dict, suggested_roles: list):
        self.resume = parsed_resume
        self.roles = suggested_roles
        self.query_builder = QueryBuilder(parsed_resume)
        self.job_service = JobSearchService()
        
    def find_jobs(self, user_preferences: dict = None) -> list:
        """
        Find jobs based on resume and user preferences
        
        Args:
            user_preferences: Dict with location, job_type, remote_filter, etc.
            
        Returns:
            List of job objects with match scores
        """
        # Build filters from resume + preferences
        filters = self.query_builder.build_filters(user_preferences)
        
        # Get role names
        role_names = []
        for role in self.roles:
            if isinstance(role, dict):
                role_names.append(role.get("role", ""))
            else:
                role_names.append(role)
        
        # Build search queries
        searches = self.query_builder.get_search_keywords(role_names)
        
        print(f"🔎 Searching for roles: {role_names}")
        print(f"📍 Location: {filters.location}")
        print(f"💼 Experience: {filters.experience_level}")
        print(f"🏠 Work mode: {filters.remote_filter or 'Any'}")
        
        # Check if job service is available
        if not self.job_service.is_available:
            print("⚠️ Job service not running. Start it with: cd scripts && npm start")
            return []
        
        # Perform batch search
        jobs = self.job_service.batch_search(searches, filters)
        
        # Add skill match scores
        my_skills = set(
            self.resume.get("skills", {}).get("technical", []) +
            self.resume.get("skills", {}).get("frameworks", []) +
            self.resume.get("skills", {}).get("tools", [])
        )
        my_skills = {s.lower() for s in my_skills}
        
        for job in jobs:
            # Simple skill matching from job title
            job_text = f"{job.get('title', '')} {job.get('company', '')}".lower()
            matches = sum(1 for skill in my_skills if skill.lower() in job_text)
            job["skill_match_count"] = matches
            
        # Sort by skill match count
        jobs.sort(key=lambda x: x.get("skill_match_count", 0), reverse=True)
        
        return jobs


def start_job_service():
    """Start the Node.js job service if not running"""
    import shutil
    
    # Check if npm is available
    npm_path = shutil.which("npm")
    if not npm_path:
        print("❌ npm not found. Please install Node.js")
        return False
    
    scripts_dir = os.path.join(os.path.dirname(__file__), "..", "scripts")
    
    # Install dependencies if needed
    node_modules = os.path.join(scripts_dir, "node_modules")
    if not os.path.exists(node_modules):
        print("📦 Installing Node.js dependencies...")
        subprocess.run(["npm", "install"], cwd=scripts_dir, shell=True)
    
    # Start the service
    print("🚀 Starting job service...")
    subprocess.Popen(
        ["npm", "start"],
        cwd=scripts_dir,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Wait for service to be ready
    import time
    for _ in range(10):
        time.sleep(1)
        try:
            response = requests.get(f"{JOB_SERVICE_URL}/health", timeout=1)
            if response.status_code == 200:
                print("✅ Job service is ready!")
                return True
        except:
            pass
    
    print("⚠️ Job service failed to start")
    return False


# Testing
if __name__ == "__main__":
    # Sample resume data
    sample_resume = {
        "personal": {"name": "Test User"},
        "total_experience_years": 2,
        "skills": {
            "technical": ["Python", "JavaScript", "SQL"],
            "frameworks": ["React", "Django", "Flask"],
            "tools": ["Git", "Docker", "AWS"]
        }
    }
    
    sample_roles = [
        {"role": "Software Engineer", "match_percent": 85},
        {"role": "Full Stack Developer", "match_percent": 75}
    ]
    
    finder = SmartJobFinder(sample_resume, sample_roles)
    
    jobs = finder.find_jobs({
        "location": "India",
        "job_type": "full time",
        "remote_filter": "remote"
    })
    
    print(f"\n📋 Found {len(jobs)} jobs:")
    for job in jobs[:5]:
        print(f"  - {job['title']} @ {job['company']} ({job.get('posted_ago', 'N/A')})")
