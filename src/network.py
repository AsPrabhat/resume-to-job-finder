# network.py - finds people at companies who might help with referrals

import requests
import os
import json
import time
import re
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple


class ConnectionCache:
    # caches search results so we dont hit API limits
    
    def __init__(self, cache_file: str = "data/connection_cache.json", ttl_hours: int = 24):
        self.cache_file = Path(cache_file)
        self.ttl_hours = ttl_hours
        self.cache = self._load_cache()
    
    def _load_cache(self) -> dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cache(self):
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2)
    
    def _get_key(self, company: str, search_type: str) -> str:
        raw_key = f"{company.lower().strip()}:{search_type}"
        return hashlib.md5(raw_key.encode()).hexdigest()
    
    def get(self, company: str, search_type: str) -> Optional[List[Dict]]:
        key = self._get_key(company, search_type)
        if key in self.cache:
            entry = self.cache[key]
            cached_time = datetime.fromisoformat(entry['timestamp'])
            if datetime.now() - cached_time < timedelta(hours=self.ttl_hours):
                return entry['data']
        return None
    
    def set(self, company: str, search_type: str, data: List[Dict]):
        key = self._get_key(company, search_type)
        self.cache[key] = {
            'timestamp': datetime.now().isoformat(),
            'company': company,
            'search_type': search_type,
            'data': data
        }
        self._save_cache()


class ConnectionScorer:
    # scores how good a connection is based on skills, seniority etc
    
    # Seniority keywords for level detection
    SENIORITY_LEVELS = {
        'intern': 1,
        'trainee': 1,
        'junior': 2,
        'associate': 2,
        'analyst': 2,
        'engineer': 3,
        'developer': 3,
        'senior': 4,
        'lead': 5,
        'staff': 5,
        'principal': 6,
        'manager': 6,
        'director': 7,
        'vp': 8,
        'vice president': 8,
        'head': 7,
        'cto': 9,
        'ceo': 9,
        'founder': 9,
        'co-founder': 9,
        'chief': 9
    }
    
    def __init__(self, job_title: str = "", job_skills: List[str] = None, target_seniority: int = 3):
        self.job_title = job_title.lower()
        self.job_skills = [s.lower() for s in (job_skills or [])]
        self.target_seniority = target_seniority
    
    def _extract_seniority(self, title: str) -> int:
        title_lower = title.lower()
        max_level = 3  # Default to mid-level
        
        for keyword, level in self.SENIORITY_LEVELS.items():
            if keyword in title_lower:
                max_level = max(max_level, level)
        
        return max_level
    
    def _calculate_skill_match(self, profile_text: str) -> float:
        if not self.job_skills:
            return 0.5  # Default if no skills provided
        
        profile_lower = profile_text.lower()
        matched = sum(1 for skill in self.job_skills if skill in profile_lower)
        return matched / len(self.job_skills) if self.job_skills else 0.5
    
    def _calculate_role_relevance(self, title: str) -> float:
        if not self.job_title:
            return 0.5
        
        title_lower = title.lower()
        job_words = set(self.job_title.split())
        title_words = set(title_lower.split())
        
        # Common role words to match
        common_words = job_words.intersection(title_words)
        if len(job_words) == 0:
            return 0.5
        
        return len(common_words) / len(job_words)
    
    def _calculate_seniority_fit(self, title: str) -> float:
        profile_seniority = self._extract_seniority(title)
        
        # People at or above target seniority are ideal connections
        if profile_seniority >= self.target_seniority:
            return 1.0
        elif profile_seniority == self.target_seniority - 1:
            return 0.7
        else:
            return 0.4
    
    def score_connection(self, connection: Dict) -> Dict:
        # adds quality scores to connection
        title = connection.get('title', connection.get('name', ''))
        profile_text = f"{title} {connection.get('snippet', '')}"
        
        # Calculate individual scores
        skill_match = self._calculate_skill_match(profile_text)
        seniority_fit = self._calculate_seniority_fit(title)
        role_relevance = self._calculate_role_relevance(title)
        
        # weighted quality score
        quality_score = (
            seniority_fit * 40 +
            skill_match * 35 +
            role_relevance * 25
        )
        
        # Add scores to connection
        connection['quality_score'] = round(quality_score, 1)
        connection['skill_match_score'] = round(skill_match * 100, 1)
        connection['seniority_score'] = round(seniority_fit * 100, 1)
        connection['relevance_score'] = round(role_relevance * 100, 1)
        connection['detected_seniority'] = self._extract_seniority(title)
        
        return connection


class NetworkFinder:
    # searches for people at companies, prioritizing IIT alumni
    
    # All IIT institutions for extended alumni search
    ALL_IITS = [
        "IIT Hyderabad", "IIT Bombay", "IIT Delhi", "IIT Madras", "IIT Kanpur",
        "IIT Kharagpur", "IIT Roorkee", "IIT Guwahati", "IIT BHU", "IIT Indore",
        "IIT Ropar", "IIT Patna", "IIT Gandhinagar", "IIT Jodhpur", "IIT Mandi",
        "IIT Bhubaneswar", "IIT Tirupati", "IIT Palakkad", "IIT Dharwad", "IIT Bhilai",
        "IIT Goa", "IIT Jammu", "IITH"
    ]
    
    # Top universities for fallback (can be customized)
    TOP_INSTITUTIONS = [
        "NIT", "BITS Pilani", "IIIT", "VIT", "SRM", "DTU", "NSIT", "RVCE",
        "IISc", "ISB", "IIM", "Stanford", "MIT", "CMU", "Berkeley"
    ]
    
    def __init__(self, primary_university: str = "IIT Hyderabad"):
        self.primary_university = primary_university
        self.api_key = os.getenv("SERPER_API_KEY")
        self.cache = ConnectionCache()
        self.scorer = None  # Set per job
        
        if not self.api_key:
            print("Warning: SERPER_API_KEY not found")
    
    def _search_serper(self, query: str, num_results: int = 10) -> List[Dict]:
        # search using serper api
        if not self.api_key:
            return []
        
        url = "https://google.serper.dev/search"
        payload = json.dumps({
            "q": query,
            "num": num_results
        })
        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(url, headers=headers, data=payload, timeout=10)
            data = response.json()
            return data.get("organic", [])
        except Exception as e:
            print(f"Serper error: {e}")
            return []
    
    def _parse_linkedin_result(self, item: Dict, connection_type: str, tier: int) -> Optional[Dict]:
        # parse linkedin result
        link = item.get("link", "")
        
        # Only process LinkedIn profile links
        if "linkedin.com/in" not in link:
            return None
        
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        
        # Extract name from title: "John Doe - Software Engineer - Company | LinkedIn"
        name_match = re.match(r'^([^-|]+)', title)
        name = name_match.group(1).strip() if name_match else title.split("-")[0].strip()
        name = name.replace("| LinkedIn", "").replace("LinkedIn", "").strip()
        
        # Extract current role from title
        role_match = re.search(r'-\s*([^-|]+)\s*-', title)
        current_role = role_match.group(1).strip() if role_match else ""
        
        # Extract company mention from title
        company_match = re.search(r'-\s*([^-|]+)\s*\|', title)
        current_company = company_match.group(1).strip() if company_match else ""
        
        return {
            "name": name,
            "title": current_role,
            "current_company": current_company,
            "profile_link": link,
            "snippet": snippet,
            "connection_type": connection_type,
            "tier": tier,
            "confidence": self._calculate_confidence(title, snippet, connection_type)
        }
    
    def _calculate_confidence(self, title: str, snippet: str, connection_type: str) -> int:
        # how confident we are this person works there
        confidence = 50
        
        # Higher confidence for alumni mentions
        if "alumni" in snippet.lower() or "graduated" in snippet.lower():
            confidence += 20
        
        # Higher confidence if IIT is mentioned
        if "iit" in snippet.lower() or "iit" in title.lower():
            confidence += 15
        
        # Higher confidence for clear LinkedIn profiles
        if " - " in title and "linkedin" in title.lower():
            confidence += 10
        
        # Tier-based confidence adjustment
        if connection_type == "Primary Alumni":
            confidence += 5
        
        return min(confidence, 100)
    
    def _search_tier(self, company: str, search_query: str, tier: int, 
                     connection_type: str, limit: int) -> List[Dict]:
        # search for connections at a tier
        
        # Check cache first
        cache_key = f"{search_query}_{tier}"
        cached = self.cache.get(company, cache_key)
        if cached is not None:
            print(f"   📦 Using cached results for Tier {tier}")
            return cached[:limit]
        
        # Execute search
        results = self._search_serper(search_query, num_results=limit + 5)
        
        # Parse results
        connections = []
        for item in results:
            conn = self._parse_linkedin_result(item, connection_type, tier)
            if conn:
                connections.append(conn)
        
        # Cache results
        self.cache.set(company, cache_key, connections)
        
        return connections[:limit]
    
    def find_connections_tiered(
        self, 
        company: str, 
        target_count: int = 3,
        job_title: str = "",
        job_skills: List[str] = None,
        include_company_employees: bool = True
    ) -> Dict:
        # multi-tier search: IITH -> all IITs -> skilled employees -> general
        
        # Initialize scorer for this job
        self.scorer = ConnectionScorer(
            job_title=job_title,
            job_skills=job_skills,
            target_seniority=3
        )
        
        all_connections = []
        tier_stats = {
            "tier_1_count": 0,
            "tier_2_count": 0,
            "tier_3_count": 0,
            "tier_4_count": 0
        }
        
        # Clean company name
        company_clean = company.strip()
        
        # Tier 1: Primary University Alumni
        print(f"   Searching {self.primary_university} alumni at {company_clean}...")
        
        tier1_query = f'site:linkedin.com/in "{company_clean}" "{self.primary_university}"'
        tier1_connections = self._search_tier(
            company_clean, tier1_query, 1, "Primary Alumni", target_count
        )
        
        for conn in tier1_connections:
            conn = self.scorer.score_connection(conn)
            all_connections.append(conn)
        
        tier_stats["tier_1_count"] = len(tier1_connections)
        remaining = target_count - len(tier1_connections)
        
        # Tier 2: All IIT Alumni
        if remaining > 0:
            print(f"   Searching all IIT alumni at {company_clean}...")
            
            # Search with "IIT" keyword to catch all IIT alumni
            tier2_query = f'site:linkedin.com/in "{company_clean}" "IIT" -"{self.primary_university}"'
            tier2_connections = self._search_tier(
                company_clean, tier2_query, 2, "IIT Alumni", remaining + 3
            )
            
            # Avoid duplicates
            existing_links = {c['profile_link'] for c in all_connections}
            for conn in tier2_connections:
                if conn['profile_link'] not in existing_links:
                    conn = self.scorer.score_connection(conn)
                    all_connections.append(conn)
                    existing_links.add(conn['profile_link'])
                    if len(all_connections) >= target_count:
                        break
            
            tier_stats["tier_2_count"] = len([c for c in all_connections if c['tier'] == 2])
            remaining = target_count - len(all_connections)
        
        # Tier 3: Company Employees with Relevant Skills
        if remaining > 0 and include_company_employees and job_skills:
            print(f"   Searching skilled employees at {company_clean}...")
            
            # Use top 3 skills for search
            top_skills = job_skills[:3] if job_skills else []
            skills_query = " OR ".join([f'"{s}"' for s in top_skills])
            tier3_query = f'site:linkedin.com/in "{company_clean}" ({skills_query})'
            
            tier3_connections = self._search_tier(
                company_clean, tier3_query, 3, "Skilled Employee", remaining + 3
            )
            
            existing_links = {c['profile_link'] for c in all_connections}
            for conn in tier3_connections:
                if conn['profile_link'] not in existing_links:
                    conn = self.scorer.score_connection(conn)
                    all_connections.append(conn)
                    existing_links.add(conn['profile_link'])
                    if len(all_connections) >= target_count:
                        break
            
            tier_stats["tier_3_count"] = len([c for c in all_connections if c['tier'] == 3])
            remaining = target_count - len(all_connections)
        
        # Tier 4: General Company Employees
        if remaining > 0 and include_company_employees:
            print(f"   Searching employees at {company_clean}...")
            
            tier4_query = f'site:linkedin.com/in "{company_clean}" employee OR engineer OR manager'
            tier4_connections = self._search_tier(
                company_clean, tier4_query, 4, "Company Employee", remaining + 3
            )
            
            existing_links = {c['profile_link'] for c in all_connections}
            for conn in tier4_connections:
                if conn['profile_link'] not in existing_links:
                    conn = self.scorer.score_connection(conn)
                    all_connections.append(conn)
                    existing_links.add(conn['profile_link'])
                    if len(all_connections) >= target_count:
                        break
            
            tier_stats["tier_4_count"] = len([c for c in all_connections if c['tier'] == 4])
        
        # Sort by quality score and tier priority
        all_connections.sort(key=lambda x: (-x['tier'], -x.get('quality_score', 0)), reverse=True)
        all_connections.sort(key=lambda x: (x['tier'], -x.get('quality_score', 0)))
        
        return {
            "connections": all_connections[:target_count],
            "total_found": len(all_connections),
            "tier_stats": tier_stats,
            "search_company": company_clean,
            "primary_university": self.primary_university
        }
    
    def find_people(self, company: str, university: str = "IIT Hyderabad", limit: int = 3,
                    job_title: str = "", job_skills: List[str] = None) -> List[Dict]:
        # older method, uses tiered search internally
        self.primary_university = university
        
        result = self.find_connections_tiered(
            company=company,
            target_count=limit,
            job_title=job_title,
            job_skills=job_skills,
            include_company_employees=True
        )
        
        return result["connections"]


class BatchNetworkFinder:
    # finds connections for multiple jobs at once
    
    def __init__(self, primary_university: str = "IIT Hyderabad"):
        self.finder = NetworkFinder(primary_university)
    
    def find_for_jobs(
        self, 
        jobs: List[Dict], 
        connections_per_job: int = 3,
        job_skills: List[str] = None
    ) -> Dict[str, List[Dict]]:
        # find connections for multiple jobs
        
        # Group jobs by company
        company_jobs = {}
        for job in jobs:
            company = job.get('company', '').strip()
            if company:
                if company not in company_jobs:
                    company_jobs[company] = []
                company_jobs[company].append(job)
        
        # Find connections for each company
        results = {}
        for company, company_job_list in company_jobs.items():
            # Use first job's title for relevance scoring
            first_job = company_job_list[0]
            job_title = first_job.get('title', first_job.get('position', ''))
            
            # Combine skills from job and global skills
            combined_skills = list(job_skills) if job_skills else []
            
            print(f"Finding connections at {company}...")
            
            result = self.finder.find_connections_tiered(
                company=company,
                target_count=connections_per_job,
                job_title=job_title,
                job_skills=combined_skills,
                include_company_employees=True
            )
            
            results[company] = result["connections"]
            
            # print summary
            stats = result["tier_stats"]
            print(f"   Found: {stats['tier_1_count']} IITH, "
                  f"{stats['tier_2_count']} IIT, "
                  f"{stats['tier_3_count']} skilled, "
                  f"{stats['tier_4_count']} other")
        
        return results


# helper function
def find_connections(company: str, university: str = "IIT Hyderabad", 
                     limit: int = 3, job_title: str = "", 
                     job_skills: List[str] = None) -> List[Dict]:
    finder = NetworkFinder(university)
    return finder.find_people(company, university, limit, job_title, job_skills)