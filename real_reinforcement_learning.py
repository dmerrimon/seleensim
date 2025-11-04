#!/usr/bin/env python3
"""
REAL Reinforcement Learning System for Ilana
Implements actual RL algorithms to learn from user feedback
"""

import os
import json
import logging
import sqlite3
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict
import pickle

logger = logging.getLogger(__name__)

@dataclass
class FeedbackEvent:
    """Individual feedback event from user interaction"""
    session_id: str
    issue_id: str
    action: str  # 'accepted', 'ignored', 'modified'
    timestamp: str
    issue_type: str
    original_text: str
    suggested_text: str
    user_context: Dict[str, Any]
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FeedbackEvent':
        return cls(
            session_id=data.get('sessionId', ''),
            issue_id=data.get('issueId', ''),
            action=data.get('action', ''),
            timestamp=data.get('timestamp', ''),
            issue_type=data.get('feedbackData', {}).get('issueType', 'clarity'),
            original_text=data.get('feedbackData', {}).get('originalText', ''),
            suggested_text=data.get('feedbackData', {}).get('suggestedText', ''),
            user_context=data.get('userContext', {})
        )

@dataclass 
class RLModelState:
    """Current state of the RL model"""
    model_version: str
    total_feedback_events: int
    acceptance_rate: float
    issue_type_performance: Dict[str, float]
    confidence_weights: Dict[str, float]
    last_updated: str
    learning_rate: float

class RealReinforcementLearning:
    """ACTUAL Reinforcement Learning implementation"""
    
    def __init__(self):
        self.db_path = "data/ilana_rl.db"
        self.model_path = "models/rl_weights.pkl"
        self.learning_rate = 0.1
        self.decay_factor = 0.95
        
        # RL State-Action Values (Q-Learning)
        self.q_values = defaultdict(lambda: defaultdict(float))
        self.state_counts = defaultdict(int)
        self.action_counts = defaultdict(lambda: defaultdict(int))
        
        # Performance tracking
        self.acceptance_rates = defaultdict(list)
        self.confidence_scores = defaultdict(float)
        
        self._initialize_database()
        self._load_model_state()
        
        logger.info("🧠 Real Reinforcement Learning system initialized")
    
    def _initialize_database(self):
        """Initialize SQLite database for feedback storage"""
        os.makedirs("data", exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    issue_id TEXT,
                    action TEXT,
                    timestamp TEXT,
                    issue_type TEXT,
                    original_text TEXT,
                    suggested_text TEXT,
                    user_context TEXT,
                    processed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    issue_type TEXT,
                    total_suggestions INTEGER,
                    accepted_suggestions INTEGER,
                    acceptance_rate REAL,
                    confidence_score REAL,
                    model_version TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rl_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    state_key TEXT UNIQUE,
                    q_values TEXT,
                    visit_count INTEGER,
                    last_reward REAL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
        
        logger.info("✅ RL database initialized")
    
    def _load_model_state(self):
        """Load existing RL model weights and Q-values"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    model_data = pickle.load(f)
                    self.q_values = model_data.get('q_values', defaultdict(lambda: defaultdict(float)))
                    self.acceptance_rates = model_data.get('acceptance_rates', defaultdict(list))
                    self.confidence_scores = model_data.get('confidence_scores', defaultdict(float))
                    logger.info("✅ Loaded existing RL model state")
            else:
                logger.info("🆕 Starting with fresh RL model")
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to load RL model state: {e}")
    
    def _save_model_state(self):
        """Save current RL model state"""
        try:
            os.makedirs("models", exist_ok=True)
            
            model_data = {
                'q_values': dict(self.q_values),
                'acceptance_rates': dict(self.acceptance_rates),
                'confidence_scores': dict(self.confidence_scores),
                'last_saved': datetime.utcnow().isoformat(),
                'model_version': f"rl_v{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            }
            
            with open(self.model_path, 'wb') as f:
                pickle.dump(model_data, f)
                
            logger.info("✅ RL model state saved")
            
        except Exception as e:
            logger.error(f"❌ Failed to save RL model state: {e}")
    
    async def process_feedback(self, feedback_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process user feedback and update RL model"""
        
        try:
            # Parse feedback event
            feedback_event = FeedbackEvent.from_dict(feedback_data)
            
            # Store in database
            self._store_feedback_event(feedback_event)
            
            # Update RL model
            reward = self._calculate_reward(feedback_event)
            state = self._encode_state(feedback_event)
            action = feedback_event.action
            
            # Q-Learning update
            self._update_q_values(state, action, reward)
            
            # Update performance metrics
            self._update_performance_metrics(feedback_event)
            
            # Save model state
            self._save_model_state()
            
            # Generate learning insights
            insights = self._generate_learning_insights(feedback_event)
            
            logger.info(f"🧠 Processed RL feedback: {feedback_event.action} for {feedback_event.issue_type}")
            
            return {
                'status': 'processed',
                'reward': reward,
                'state': state,
                'learning_insights': insights,
                'model_updated': True,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ RL feedback processing failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'model_updated': False
            }
    
    def _store_feedback_event(self, event: FeedbackEvent):
        """Store feedback event in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO feedback_events 
                (session_id, issue_id, action, timestamp, issue_type, 
                 original_text, suggested_text, user_context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.session_id,
                event.issue_id, 
                event.action,
                event.timestamp,
                event.issue_type,
                event.original_text,
                event.suggested_text,
                json.dumps(event.user_context)
            ))
            conn.commit()
    
    def _calculate_reward(self, feedback_event: FeedbackEvent) -> float:
        """Calculate reward signal for RL"""
        
        base_reward = 0.0
        
        # Action-based rewards
        if feedback_event.action == 'accepted':
            base_reward = 1.0
        elif feedback_event.action == 'ignored':
            base_reward = -0.5
        elif feedback_event.action == 'modified':
            base_reward = 0.3  # Partial credit
        
        # Issue type modifiers
        type_modifier = {
            'clarity': 1.0,
            'compliance': 1.2,  # Higher value for compliance
            'feasibility': 0.8   # Lower value (disabled)
        }.get(feedback_event.issue_type, 1.0)
        
        # Context modifiers
        context_modifier = 1.0
        if feedback_event.user_context.get('documentLength', 0) > 50000:
            context_modifier *= 1.1  # Bonus for large documents
        
        final_reward = base_reward * type_modifier * context_modifier
        
        # Add exploration bonus for less-visited states
        state = self._encode_state(feedback_event)
        visit_bonus = 0.1 / (1 + self.state_counts[state])
        
        return final_reward + visit_bonus
    
    def _encode_state(self, feedback_event: FeedbackEvent) -> str:
        """Encode feedback context into RL state"""
        
        # Create state representation
        text_length_bucket = 'short' if len(feedback_event.original_text) < 50 else 'medium' if len(feedback_event.original_text) < 200 else 'long'
        doc_size_bucket = 'small' if feedback_event.user_context.get('documentLength', 0) < 10000 else 'medium' if feedback_event.user_context.get('documentLength', 0) < 50000 else 'large'
        
        state = f"{feedback_event.issue_type}_{text_length_bucket}_{doc_size_bucket}"
        return state
    
    def _update_q_values(self, state: str, action: str, reward: float):
        """Update Q-values using Q-learning algorithm"""
        
        # Q-Learning update: Q(s,a) = Q(s,a) + α[r + γ max Q(s',a') - Q(s,a)]
        # Simplified: Q(s,a) = Q(s,a) + α[r - Q(s,a)]
        
        current_q = self.q_values[state][action]
        self.q_values[state][action] = current_q + self.learning_rate * (reward - current_q)
        
        # Update counts
        self.state_counts[state] += 1
        self.action_counts[state][action] += 1
        
        # Decay learning rate over time
        self.learning_rate *= self.decay_factor
        self.learning_rate = max(0.01, self.learning_rate)  # Minimum learning rate
    
    def _update_performance_metrics(self, feedback_event: FeedbackEvent):
        """Update performance tracking metrics"""
        
        issue_type = feedback_event.issue_type
        
        # Update acceptance rates
        is_accepted = 1.0 if feedback_event.action == 'accepted' else 0.0
        self.acceptance_rates[issue_type].append(is_accepted)
        
        # Keep only recent history (last 100 events per type)
        if len(self.acceptance_rates[issue_type]) > 100:
            self.acceptance_rates[issue_type] = self.acceptance_rates[issue_type][-100:]
        
        # Update confidence scores based on recent performance
        if len(self.acceptance_rates[issue_type]) >= 5:
            recent_acceptance = np.mean(self.acceptance_rates[issue_type][-20:])
            self.confidence_scores[issue_type] = recent_acceptance
    
    def _generate_learning_insights(self, feedback_event: FeedbackEvent) -> Dict[str, Any]:
        """Generate insights about what the model is learning"""
        
        issue_type = feedback_event.issue_type
        state = self._encode_state(feedback_event)
        
        insights = {
            'issue_type_performance': {},
            'state_quality': {},
            'learning_trends': {},
            'recommendations': []
        }
        
        # Issue type performance
        for itype in ['clarity', 'compliance']:
            if itype in self.acceptance_rates:
                rates = self.acceptance_rates[itype]
                if len(rates) >= 5:
                    insights['issue_type_performance'][itype] = {
                        'acceptance_rate': float(np.mean(rates)),
                        'total_feedback': len(rates),
                        'confidence': self.confidence_scores.get(itype, 0.5),
                        'trend': 'improving' if len(rates) >= 10 and np.mean(rates[-5:]) > np.mean(rates[-10:-5]) else 'stable'
                    }
        
        # State quality assessment
        if state in self.q_values:
            state_q_values = dict(self.q_values[state])
            insights['state_quality'][state] = {
                'q_values': state_q_values,
                'visits': self.state_counts[state],
                'best_action': max(state_q_values.items(), key=lambda x: x[1])[0] if state_q_values else 'unknown'
            }
        
        # Learning recommendations
        if self.confidence_scores.get(issue_type, 0) < 0.6:
            insights['recommendations'].append(f"Consider improving {issue_type} suggestions - low acceptance rate")
        
        if self.state_counts[state] < 5:
            insights['recommendations'].append(f"Need more feedback for state: {state}")
        
        return insights
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary for team dashboard"""
        
        summary = {
            'model_status': {
                'version': f"rl_v{datetime.utcnow().strftime('%Y%m%d')}",
                'total_states': len(self.q_values),
                'total_feedback_events': sum(self.state_counts.values()),
                'learning_rate': self.learning_rate,
                'last_updated': datetime.utcnow().isoformat()
            },
            'performance_by_type': {},
            'top_performing_states': {},
            'learning_insights': []
        }
        
        # Performance by issue type
        for issue_type in ['clarity', 'compliance']:
            if issue_type in self.acceptance_rates:
                rates = self.acceptance_rates[issue_type]
                if rates:
                    summary['performance_by_type'][issue_type] = {
                        'acceptance_rate': float(np.mean(rates)),
                        'total_suggestions': len(rates),
                        'confidence_score': self.confidence_scores.get(issue_type, 0.5),
                        'recent_trend': 'improving' if len(rates) >= 10 and np.mean(rates[-5:]) > np.mean(rates[-10:-5]) else 'stable'
                    }
        
        # Top performing states
        state_performance = {}
        for state, actions in self.q_values.items():
            if actions and self.state_counts[state] >= 3:
                avg_q = np.mean(list(actions.values()))
                state_performance[state] = {
                    'avg_q_value': avg_q,
                    'visits': self.state_counts[state],
                    'best_action': max(actions.items(), key=lambda x: x[1])[0]
                }
        
        # Sort by performance and take top 5
        top_states = sorted(state_performance.items(), key=lambda x: x[1]['avg_q_value'], reverse=True)[:5]
        summary['top_performing_states'] = dict(top_states)
        
        # Generate insights
        total_feedback = sum(self.state_counts.values())
        if total_feedback > 50:
            summary['learning_insights'].append("Model has sufficient data for reliable predictions")
        else:
            summary['learning_insights'].append("Model needs more feedback data to improve accuracy")
        
        overall_acceptance = np.mean([np.mean(rates) for rates in self.acceptance_rates.values() if rates])
        if overall_acceptance > 0.7:
            summary['learning_insights'].append("High user satisfaction - model performing well")
        elif overall_acceptance > 0.5:
            summary['learning_insights'].append("Moderate performance - room for improvement")
        else:
            summary['learning_insights'].append("Low acceptance rate - model needs significant improvement")
        
        return summary

# Global RL instance
_rl_instance = None

def get_rl_instance() -> RealReinforcementLearning:
    """Get singleton RL instance"""
    global _rl_instance
    if _rl_instance is None:
        _rl_instance = RealReinforcementLearning()
    return _rl_instance