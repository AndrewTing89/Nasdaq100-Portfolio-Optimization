#!/usr/bin/env python3
"""
Pipeline Wrapper - Allows switching between CSV-based and API-based pipelines
"""

import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class PipelineWrapper:
    """Wrapper to switch between different pipeline implementations"""
    
    def __init__(self, data_dir: str = "/data"):
        self.data_dir = data_dir
        
        # Check environment variable to determine which pipeline to use
        self.use_api = os.environ.get('USE_API_PIPELINE', 'false').lower() == 'true'
        
        if self.use_api:
            logger.info("Using API-based pipeline (FMP)")
            from data_pipeline import DataPipeline, Config
            config = Config.from_env()
            self.pipeline = DataPipeline(config)
        else:
            logger.info("Using CSV-based pipeline (local files)")
            from simplified_pipeline import SimplifiedPipeline
            self.pipeline = SimplifiedPipeline(data_dir)
    
    def health_check(self) -> Dict[str, Any]:
        """Health check"""
        return self.pipeline.health_check()
    
    def run_phase1(self) -> Dict[str, Any]:
        """Run Phase 1"""
        if self.use_api:
            return self.pipeline.run_phase1_nasdaq_analysis()
        else:
            return self.pipeline.run_phase1()
    
    def run_phase2(self) -> Dict[str, Any]:
        """Run Phase 2"""
        if self.use_api:
            return self.pipeline.run_phase2_stock_data_fetching()
        else:
            return self.pipeline.run_phase2()
    
    def run_phase3(self, model_type: str = "all") -> Dict[str, Any]:
        """Run Phase 3"""
        if self.use_api:
            return self.pipeline.run_phase3_portfolio_optimization(
                input_file=None, 
                model_type=model_type, 
                return_type="both"
            )
        else:
            return self.pipeline.run_phase3(model_type=model_type)
    
    def run_full_pipeline(self) -> Dict[str, Any]:
        """Run full pipeline"""
        if self.use_api:
            return self.pipeline.run_full_pipeline(
                model_type="all", 
                return_type="both"
            )
        else:
            return self.pipeline.run_full_pipeline()