import os
from pypdf import PdfReader
from openai import OpenAI
import json
from dotenv import load_dotenv

load_dotenv()

class ResumeAnalyzer:
    def __init__(self):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
        self.parsed_resume = None  # Store structured data

    def extract_text(self, pdf_path):
        # get text from pdf
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return None

    def parse_resume_structured(self, resume_text):
        # parse resume into json structure
        print("Extracting data from resume...")
        
        prompt = f"""You are an expert resume parser. Analyze the following resume and extract ALL information into a structured JSON format.

Resume Text:
{resume_text[:6000]}

Extract and return ONLY valid JSON in this exact format (no markdown, no extra text):
{{
    "personal": {{
        "name": "Full Name",
        "email": "email if found",
        "phone": "phone if found",
        "location": "city/country if found",
        "linkedin": "linkedin url if found",
        "github": "github url if found",
        "portfolio": "portfolio url if found"
    }},
    "summary": "2-3 sentence professional summary based on the resume",
    "skills": {{
        "technical": ["Python", "JavaScript", "etc"],
        "frameworks": ["React", "Django", "etc"],
        "tools": ["Git", "Docker", "AWS", "etc"],
        "soft_skills": ["Leadership", "Communication", "etc"],
        "languages": ["English", "Hindi", "etc"]
    }},
    "experience": [
        {{
            "title": "Job Title",
            "company": "Company Name",
            "location": "City, Country",
            "start_date": "Month Year",
            "end_date": "Month Year or Present",
            "duration_months": 12,
            "highlights": ["Achievement 1", "Achievement 2"],
            "technologies_used": ["Python", "AWS"]
        }}
    ],
    "education": [
        {{
            "degree": "B.Tech in Computer Science",
            "institution": "University Name",
            "location": "City, Country",
            "graduation_year": "2023",
            "gpa": "8.5/10 if mentioned",
            "highlights": ["Relevant coursework", "Honors"]
        }}
    ],
    "projects": [
        {{
            "name": "Project Name",
            "description": "Brief description",
            "technologies": ["React", "Node.js"],
            "url": "github/demo link if available",
            "highlights": ["Key achievement or metric"]
        }}
    ],
    "certifications": [
        {{
            "name": "Certification Name",
            "issuer": "Issuing Organization",
            "date": "Month Year",
            "credential_id": "ID if mentioned"
        }}
    ],
    "achievements": ["Award 1", "Recognition 2", "Publication 3"],
    "total_experience_years": 2.5,
    "career_level": "Entry/Mid/Senior/Lead/Executive"
}}

Important:
- Extract ALL skills mentioned, even implicitly from project/experience descriptions
- Calculate total experience in years from work history
- Determine career level based on roles and experience
- If information is not found, use null or empty array
- Return ONLY the JSON, no explanations"""

        response = self.client.chat.completions.create(
            model="xiaomi/mimo-v2-flash:free",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1  # Low temperature for consistent extraction
        )

        try:
            content = response.choices[0].message.content
            content = content.replace("```json", "").replace("```", "").strip()
            self.parsed_resume = json.loads(content)
            print("Resume parsed")
            return self.parsed_resume
        except Exception as e:
            print(f"Error parsing structured resume: {e}")
            return None

    def get_suggested_roles(self, resume_text=None, parsed_data=None, n=3):
        # suggest job roles based on resume
        print("Finding best job roles...")
        
        # Use parsed data if available, otherwise parse first
        if parsed_data is None and self.parsed_resume is None:
            if resume_text:
                self.parse_resume_structured(resume_text)
            else:
                return []
        
        data = parsed_data or self.parsed_resume
        
        prompt = f"""You are a senior career counselor and technical recruiter with 20 years of experience.

Analyze this candidate's profile and recommend the {n} BEST job roles for them.

CANDIDATE PROFILE:
{json.dumps(data, indent=2)}

For each role, provide:
1. The exact job title (be specific, e.g., "Backend Software Engineer" not just "Engineer")
2. Match percentage (how well they fit based on skills, experience, career trajectory)
3. Detailed reasoning (why this role suits them)
4. Skills they already have for this role
5. Skills gaps they should work on
6. Salary range expectation (use market data for their experience level)

Return ONLY valid JSON in this format:
[
    {{
        "role": "Specific Job Title",
        "match_percent": 85,
        "reasoning": "Detailed 2-3 sentence explanation of why this role is a great fit",
        "matching_skills": ["skill1", "skill2", "skill3"],
        "skills_to_develop": ["skill1", "skill2"],
        "experience_fit": "Their X years aligns with mid-level positions...",
        "salary_range": "$80,000 - $100,000",
        "growth_potential": "High/Medium/Low with brief explanation"
    }}
]

Rank by match_percent descending. Be realistic and specific."""

        response = self.client.chat.completions.create(
            model="xiaomi/mimo-v2-flash:free",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        try:
            content = response.choices[0].message.content
            content = content.replace("```json", "").replace("```", "").strip()
            roles = json.loads(content)
            print(f"Found {len(roles)} roles")
            return roles
        except Exception as e:
            print(f"Error parsing role suggestions: {e}")
            return []

    def get_career_insights(self, parsed_data=None):
        # extra career advice
        data = parsed_data or self.parsed_resume
        if not data:
            return None
            
        print("Getting career insights...")
        
        prompt = f"""Based on this candidate's profile, provide strategic career advice:

{json.dumps(data, indent=2)}

Return JSON with:
{{
    "strengths": ["Top 3 standout qualities"],
    "areas_for_improvement": ["Top 3 areas to develop"],
    "recommended_certifications": ["2-3 certifications that would boost their profile"],
    "networking_suggestions": ["Types of communities/events to join"],
    "resume_tips": ["2-3 specific improvements for their resume"],
    "interview_topics": ["Key topics they should be prepared to discuss"],
    "career_trajectory": "Where they could be in 2-3 years with focused effort"
}}"""

        response = self.client.chat.completions.create(
            model="xiaomi/mimo-v2-flash:free",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )

        try:
            content = response.choices[0].message.content
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as e:
            print(f"Error generating insights: {e}")
            return None

    def full_analysis(self, pdf_path, n_roles=3):
        # run everything
        print("\nStarting analysis...")
        
        # Step 1: Extract text
        resume_text = self.extract_text(pdf_path)
        if not resume_text:
            return None
            
        # Step 2: Parse into structured format
        parsed = self.parse_resume_structured(resume_text)
        if not parsed:
            return None
            
        # Step 3: Get role recommendations
        roles = self.get_suggested_roles(parsed_data=parsed, n=n_roles)
        
        # Step 4: Get career insights
        insights = self.get_career_insights(parsed_data=parsed)
        
        return {
            "parsed_resume": parsed,
            "suggested_roles": roles,
            "career_insights": insights
        }


# Testing block
if __name__ == "__main__":
    analyzer = ResumeAnalyzer()
    result = analyzer.full_analysis("data/resume.pdf", n_roles=3)
    
    if result:
        print("\nDone!")
        print("Name:", result["parsed_resume"].get("personal", {}).get("name", "Unknown"))
        print("Experience:", result["parsed_resume"].get("total_experience_years", "N/A"), "years")
        
        print("\nRoles:")
        for i, role in enumerate(result["suggested_roles"], 1):
            print(f"{i}. {role['role']} ({role['match_percent']}% match)")
        
        with open("data/analysis_result.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print("\nSaved to data/analysis_result.json")