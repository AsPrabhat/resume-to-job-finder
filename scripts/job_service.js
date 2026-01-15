// job search service using linkedin-jobs-api

const express = require('express');
const cors = require('cors');
const linkedIn = require('linkedin-jobs-api');

const app = express();
app.use(cors());
app.use(express.json());

const PORT = process.env.PORT || 3001;

// health check
app.get('/health', (req, res) => {
    res.json({ status: 'ok' });
});

// search jobs
app.post('/search', async (req, res) => {
    try {
        const {
            keyword = '',
            location = 'India',
            experienceLevel = '',
            jobType = '',
            remoteFilter = '',
            dateSincePosted = 'past week',
            salary = '',
            limit = 10,
            page = 0,
            skills = [],
            sortBy = 'recent'
        } = req.body;

        // add skills to keyword
        let enhancedKeyword = keyword;
        if (skills && skills.length > 0) {
            const topSkills = skills.slice(0, 3).join(' ');
            enhancedKeyword = `${keyword} ${topSkills}`.trim();
        }

        const queryOptions = {
            keyword: enhancedKeyword,
            location: location,
            dateSincePosted: dateSincePosted,
            jobType: jobType,
            remoteFilter: remoteFilter,
            salary: salary,
            experienceLevel: experienceLevel,
            limit: String(limit),
            page: String(page),
            sortBy: sortBy
        };

        // remove empty values
        Object.keys(queryOptions).forEach(key => {
            if (queryOptions[key] === '' || queryOptions[key] === null || queryOptions[key] === undefined) {
                delete queryOptions[key];
            }
        });

        console.log(`Searching: ${keyword}`);

        const jobs = await linkedIn.query(queryOptions);

        console.log(`Found ${jobs.length} jobs`);

        // format response
        const transformedJobs = jobs.map(job => ({
            title: job.position || '',
            company: job.company || '',
            company_logo: job.companyLogo || '',
            location: job.location || '',
            posted_date: job.date || '',
            posted_ago: job.agoTime || '',
            salary: job.salary || '',
            link: job.jobUrl || '',
            source: 'linkedin',
            search_keyword: keyword
        }));

        res.json({
            success: true,
            count: transformedJobs.length,
            query: queryOptions,
            jobs: transformedJobs
        });

    } catch (error) {
        console.error(`Error: ${error.message}`);
        res.status(500).json({
            success: false,
            error: error.message,
            jobs: []
        });
    }
});

// batch search - multiple keywords at once
app.post('/batch-search', async (req, res) => {
    try {
        const { searches = [], commonFilters = {} } = req.body;
        
        const allJobs = [];
        const errors = [];

        for (const search of searches) {
            try {
                const queryOptions = {
                    keyword: search.keyword || '',
                    location: commonFilters.location || 'India',
                    dateSincePosted: commonFilters.dateSincePosted || 'past week',
                    jobType: commonFilters.jobType || '',
                    remoteFilter: commonFilters.remoteFilter || '',
                    experienceLevel: commonFilters.experienceLevel || '',
                    limit: String(search.limit || commonFilters.limit || 5),
                    page: String(search.page || 0),
                    sortBy: commonFilters.sortBy || 'recent'
                };

                // remove empty
                Object.keys(queryOptions).forEach(key => {
                    if (!queryOptions[key]) delete queryOptions[key];
                });

                console.log(`Batch: ${search.keyword}`);

                const jobs = await linkedIn.query(queryOptions);

                const transformedJobs = jobs.map(job => ({
                    title: job.position || '',
                    company: job.company || '',
                    company_logo: job.companyLogo || '',
                    location: job.location || '',
                    posted_date: job.date || '',
                    posted_ago: job.agoTime || '',
                    salary: job.salary || '',
                    link: job.jobUrl || '',
                    source: 'linkedin',
                    search_keyword: search.keyword,
                    search_role: search.role || search.keyword
                }));

                allJobs.push(...transformedJobs);

                // delay between requests
                await new Promise(resolve => setTimeout(resolve, 500));

            } catch (err) {
                errors.push({ keyword: search.keyword, error: err.message });
            }
        }

        // remove duplicates
        const uniqueJobs = allJobs.filter((job, index, self) =>
            index === self.findIndex(j => j.link === job.link)
        );

        res.json({
            success: true,
            total_count: uniqueJobs.length,
            jobs: uniqueJobs,
            errors: errors.length > 0 ? errors : undefined
        });

    } catch (error) {
        console.error(`Batch error: ${error.message}`);
        res.status(500).json({
            success: false,
            error: error.message,
            jobs: []
        });
    }
});

// start server
app.listen(PORT, () => {
    console.log(`Job search service running on http://localhost:${PORT}`);
});
