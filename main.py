import os
import logging
from contextlib import asynccontextmanager
from openai import OpenAI
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Dict, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up application...")
    logger.info("Checking environment variables...")
    if not all([os.getenv('OPENAI_API_KEY'), os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY')]):
        logger.error("Missing required environment variables!")
    else:
        logger.info("All required environment variables are set")
    yield
    # Shutdown
    logger.info("Shutting down application...")

# Initialize FastAPI with lifespan
app = FastAPI(lifespan=lifespan)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

class CompetitiveLandscape(BaseModel):
    competitive_summary: str
    gaps_opportunities: str

class CompetitiveLandscapeResponse(BaseModel):
    brand_name: str
    competitive_summary: str
    gaps_opportunities: str

# [Your existing functions remain unchanged]
def get_competitors_data(brand_name: str) -> List[Dict]:
    """
    Get all competitor data for the specified brand
    """
    response = supabase.table('competitors').select(
        'competitor_name, program_summary, competitor_positioning, competitor_rewards_benefits, competitor_user_feedback, competitor_strength, competitor_weakness, competitor_opportunity, competitor_threats'
    ).eq('brand_name', brand_name).execute()
    
    return response.data

def analyze_competitive_landscape(brand_name: str, competitors_data: List[Dict]) -> CompetitiveLandscape:
    """
    Analyze the competitive landscape and identify opportunities
    """
    # [Your existing implementation remains unchanged]
    competitors_overview = ""
    for comp in competitors_data:
        competitors_overview += f"""
        Competitor: {comp.get('competitor_name', 'N/A')}
        Program Summary: {comp.get('program_summary', 'N/A')}
        Market Position: {comp.get('competitor_positioning', 'N/A')}
        Rewards & Benefits: {comp.get('competitor_rewards_benefits', 'N/A')}
        User Feedback: {comp.get('competitor_user_feedback', 'N/A')}
        Strengths: {comp.get('competitor_strength', 'N/A')}
        Weaknesses: {comp.get('competitor_weakness', 'N/A')}
        Opportunities: {comp.get('competitor_opportunity', 'N/A')}
        Threats: {comp.get('competitor_threats', 'N/A')}
        ---
        """

    prompt = f"""Analyze this competitive landscape data for {brand_name}'s market:

    {competitors_overview}

    Create two comprehensive analyses:
    1. A summary of the competitive loyalty landscape using the data about the competitors loyalty programs.
    2. Specific gaps and opportunities that {brand_name} could exploit when designing their loyalty program, be very specific and reference specific examples from the competitor data.

    Consider:
    - Common strengths and weaknesses across competitors
    - Unmet customer needs
    - Market gaps
    - Innovative opportunities
    - Potential differentiation strategies"""

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-11-20",
        messages=[
            {"role": "system", "content": f"You are a strategic analyst helping {brand_name} design a competitive loyalty program."},
            {"role": "user", "content": prompt}
        ],
        response_format=CompetitiveLandscape
    )
    
    return completion.choices[0].message.parsed

def save_landscape_analysis(brand_name: str, analysis: CompetitiveLandscape):
    """
    Save the landscape analysis to the competitor_summary table
    """
    try:
        # First, check if an analysis already exists for this brand
        existing = supabase.table('competitor_summary').select('id').eq('brand_name', brand_name).execute()
        
        if existing.data:
            # Update existing analysis
            response = supabase.table('competitor_summary').update({
                'competitive_summary': analysis.competitive_summary,
                'gaps_opportunities': analysis.gaps_opportunities
            }).eq('brand_name', brand_name).execute()
        else:
            # Create new analysis
            response = supabase.table('competitor_summary').insert({
                'brand_name': brand_name,
                'competitive_summary': analysis.competitive_summary,
                'gaps_opportunities': analysis.gaps_opportunities
            }).execute()
        
        logger.info(f"Successfully saved landscape analysis for {brand_name}")
        return response.data[0]
    except Exception as e:
        logger.error(f"Error saving analysis: {str(e)}")
        raise

# FastAPI endpoints
@app.get("/")
async def root():
    logger.info("Health check endpoint called")
    return {"status": "API is running"}

@app.post("/analyze/{brand_name}", response_model=CompetitiveLandscapeResponse)
async def create_analysis(brand_name: str):
    """
    Create and save competitive landscape analysis for a brand
    """
    try:
        logger.info(f"Starting analysis for brand: {brand_name}")
        
        # Get competitor data
        competitors_data = get_competitors_data(brand_name)
        
        if not competitors_data:
            logger.error(f"No competitor data found for {brand_name}")
            raise HTTPException(status_code=404, detail="No competitor data found")
        
        logger.info(f"Found data for {len(competitors_data)} competitors")
        
        # Analyze landscape
        analysis = analyze_competitive_landscape(brand_name, competitors_data)
        
        # Save analysis
        saved_analysis = save_landscape_analysis(brand_name, analysis)
        
        return CompetitiveLandscapeResponse(
            brand_name=brand_name,
            competitive_summary=analysis.competitive_summary,
            gaps_opportunities=analysis.gaps_opportunities
        )
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
