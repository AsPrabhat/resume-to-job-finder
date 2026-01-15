from sentence_transformers import SentenceTransformer, util
import torch

class SemanticMatcher:
    def __init__(self):
        print("Loading model...")
        self.model = SentenceTransformer('all-mpnet-base-v2')

    def score_jobs(self, jobs, roles_list):
        # calculates how well each job matches the target roles
        # 1. Encode the Role Names into Vectors (The "Benchmarks")
        # e.g., Vector for "Software Engineer", Vector for "Data Scientist"
        role_embeddings = self.model.encode(roles_list, convert_to_tensor=True)

        for job in jobs:
            # 2. Encode the Job Description (The "Candidate")
            # We combine title and description for better context
            job_text = f"{job['title']} {job['description']}"
            job_embedding = self.model.encode(job_text, convert_to_tensor=True)

            # 3. Calculate Cosine Similarity against ALL roles
            # Returns a list of scores, one for each role
            cosine_scores = util.cos_sim(job_embedding, role_embeddings)[0]

            # 4. Store scores nicely
            job["role_matches"] = {}
            for idx, role_name in enumerate(roles_list):
                # Convert 0.8532 -> 85
                score_percent = int(cosine_scores[idx].item() * 100)
                job["role_matches"][role_name] = score_percent

        return jobs