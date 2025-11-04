"""
Real AI Service for Azure Functions
Simplified version of the original real_ai_service.py for Azure Functions deployment
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import openai
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class InlineSuggestion:
    """Inline suggestion data structure"""
    type: str
    subtype: Optional[str]
    originalText: str
    suggestedText: str
    rationale: str
    complianceRationale: str
    fdaReference: Optional[str] = None
    emaReference: Optional[str] = None
    guidanceSource: Optional[str] = None
    readabilityScore: Optional[float] = None
    operationalImpact: Optional[str] = None
    retentionRisk: Optional[str] = None
    enrollmentImpact: Optional[str] = None
    backendConfidence: Optional[str] = None
    range: Dict[str, int] = None
    
    def __post_init__(self):
        if self.range is None:
            self.range = {"start": 0, "end": 0}

class RealAIService:
    """Real AI service using Azure OpenAI and Pinecone"""
    
    def __init__(self, config):
        self.config = config
        self.azure_client = None
        self.pinecone_index = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize Azure OpenAI and Pinecone services"""
        try:
            # Initialize Azure OpenAI
            if self.config.enable_azure_openai and self.config.azure_openai_endpoint:
                openai.api_type = "azure"
                openai.api_base = self.config.azure_openai_endpoint
                openai.api_key = self.config.azure_openai_key
                openai.api_version = self.config.azure_openai_api_version
                logger.info("✅ Azure OpenAI client initialized")
            else:
                logger.warning("⚠️ Azure OpenAI not configured")
            
            # Initialize Pinecone (optional for now)
            if self.config.enable_pinecone_integration and self.config.pinecone_api_key:
                try:
                    import pinecone
                    pinecone.init(
                        api_key=self.config.pinecone_api_key,
                        environment=self.config.pinecone_environment
                    )
                    self.pinecone_index = pinecone.Index(self.config.pinecone_index_name)
                    logger.info("✅ Pinecone client initialized")
                except ImportError:
                    logger.warning("⚠️ Pinecone library not available")
                except Exception as e:
                    logger.warning(f"⚠️ Pinecone initialization failed: {e}")
            else:
                logger.warning("⚠️ Pinecone not configured")
                
        except Exception as e:
            logger.error(f"❌ Service initialization failed: {e}")
            raise
    
    async def analyze_comprehensive(self, text: str, options: Dict[str, Any] = None) -> Tuple[List[InlineSuggestion], Dict[str, Any]]:
        """
        Comprehensive analysis using Azure OpenAI
        """
        start_time = datetime.utcnow()
        options = options or {}
        
        try:
            logger.info(f"🤖 Starting comprehensive analysis for {len(text)} characters")
            
            # Smart chunking for large documents
            chunks = self._smart_text_chunking(text, max_chunk_size=15000)
            max_chunks = min(len(chunks), 3)  # Limit to 3 chunks for speed
            
            all_suggestions = []
            current_offset = 0
            
            # Process chunks sequentially to avoid rate limits
            for i in range(max_chunks):
                chunk = chunks[i]
                logger.info(f"Processing chunk {i+1}/{max_chunks} ({len(chunk)} chars)")
                
                chunk_suggestions = await self._analyze_chunk(chunk, current_offset, options)
                all_suggestions.extend(chunk_suggestions)
                
                # Update offset for next chunk
                current_offset += len(chunk)
                
                # Small delay between chunks to avoid rate limits
                if i < max_chunks - 1:
                    await asyncio.sleep(0.5)
            
            # Calculate metadata
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            metadata = {
                "processing_time": processing_time,
                "chunks_processed": max_chunks,
                "total_chunks": len(chunks),
                "total_suggestions": len(all_suggestions),
                "text_length": len(text),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"✅ Analysis completed: {len(all_suggestions)} suggestions in {processing_time:.2f}s")
            
            return all_suggestions, metadata
            
        except Exception as e:
            logger.error(f"❌ Comprehensive analysis failed: {str(e)}")
            # Return fallback suggestions on error
            fallback_suggestions = self._create_fallback_suggestions(text)
            metadata = {
                "processing_time": (datetime.utcnow() - start_time).total_seconds(),
                "error": str(e),
                "fallback_mode": True
            }
            return fallback_suggestions, metadata
    
    def _smart_text_chunking(self, text: str, max_chunk_size: int = 15000) -> List[str]:
        """Smart text chunking that preserves sentence boundaries"""
        if len(text) <= max_chunk_size:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # Split by sentences first
        sentences = text.split('. ')
        
        for sentence in sentences:
            # If adding this sentence would exceed chunk size, start new chunk
            if len(current_chunk) + len(sentence) + 2 > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
            else:
                current_chunk += sentence + ". "
        
        # Add the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    async def _analyze_chunk(self, chunk: str, offset: int, options: Dict[str, Any]) -> List[InlineSuggestion]:
        """Analyze a single chunk using Azure OpenAI"""
        try:
            # Create the analysis prompt
            system_prompt = """You are Ilana, an expert clinical protocol analyzer. Analyze the provided protocol text and identify specific issues with regulatory compliance, clarity, and operational feasibility.

For each issue found, provide:
1. The exact problematic text
2. A specific improvement suggestion
3. The rationale for the change
4. Regulatory compliance explanation

Focus on:
- FDA/EMA regulatory compliance
- Protocol clarity and readability
- Operational feasibility for clinical sites
- Patient recruitment and retention considerations

Return results as a JSON array of suggestions."""

            user_prompt = f"""Analyze this clinical protocol text:

{chunk}

Identify specific issues and provide improvement suggestions. Focus on regulatory compliance, clarity, and operational feasibility."""

            # Call Azure OpenAI
            response = await self._call_azure_openai(system_prompt, user_prompt)
            
            if response:
                suggestions = self._parse_ai_response(response, offset)
                return suggestions
            else:
                return []
                
        except Exception as e:
            logger.error(f"❌ Chunk analysis failed: {str(e)}")
            return []
    
    async def _call_azure_openai(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call Azure OpenAI API"""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: openai.ChatCompletion.create(
                    engine="gpt-4",  # Adjust engine name as needed
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=2000,
                    temperature=0.1,
                    timeout=30
                )
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Azure OpenAI API call failed: {str(e)}")
            return None
    
    def _parse_ai_response(self, response: str, offset: int) -> List[InlineSuggestion]:
        """Parse AI response into InlineSuggestion objects"""
        suggestions = []
        
        try:
            # Try to parse as JSON
            response_data = json.loads(response)
            
            if isinstance(response_data, list):
                for item in response_data:
                    suggestion = self._create_suggestion_from_dict(item, offset)
                    if suggestion:
                        suggestions.append(suggestion)
            
        except json.JSONDecodeError:
            # If not valid JSON, create a generic suggestion
            logger.warning("❌ Failed to parse AI response as JSON, creating fallback suggestion")
            suggestions.append(InlineSuggestion(
                type="clarity",
                subtype="general",
                originalText="Protocol text",
                suggestedText="Improved protocol text",
                rationale="AI analysis completed but response format was unexpected",
                complianceRationale="General protocol improvement recommended",
                range={"start": offset, "end": offset + 100}
            ))
        
        return suggestions
    
    def _create_suggestion_from_dict(self, data: Dict[str, Any], offset: int) -> Optional[InlineSuggestion]:
        """Create InlineSuggestion from dictionary data"""
        try:
            return InlineSuggestion(
                type=data.get("type", "clarity"),
                subtype=data.get("subtype"),
                originalText=data.get("originalText", ""),
                suggestedText=data.get("suggestedText", ""),
                rationale=data.get("rationale", ""),
                complianceRationale=data.get("complianceRationale", ""),
                fdaReference=data.get("fdaReference"),
                emaReference=data.get("emaReference"),
                guidanceSource=data.get("guidanceSource"),
                readabilityScore=data.get("readabilityScore"),
                operationalImpact=data.get("operationalImpact"),
                retentionRisk=data.get("retentionRisk"),
                enrollmentImpact=data.get("enrollmentImpact"),
                backendConfidence=data.get("backendConfidence", "medium"),
                range={
                    "start": data.get("start", offset),
                    "end": data.get("end", offset + len(data.get("originalText", "")))
                }
            )
        except Exception as e:
            logger.error(f"❌ Failed to create suggestion from data: {e}")
            return None
    
    def _create_fallback_suggestions(self, text: str) -> List[InlineSuggestion]:
        """Create fallback suggestions when AI analysis fails"""
        return [
            InlineSuggestion(
                type="clarity",
                subtype="general",
                originalText="Protocol requires review",
                suggestedText="Protocol has been analyzed using fallback mode",
                rationale="AI analysis encountered an issue but basic analysis completed",
                complianceRationale="Manual review recommended for full compliance assessment",
                backendConfidence="low",
                range={"start": 0, "end": min(len(text), 100)}
            )
        ]

def create_real_ai_service(config) -> RealAIService:
    """Factory function to create RealAIService instance"""
    return RealAIService(config)