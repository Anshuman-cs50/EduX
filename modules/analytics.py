from typing import List, Dict
import statistics
import logging

logger = logging.getLogger(__name__)

class AnalyticsEngine:
    @staticmethod
    def calculate_progress(interactions: List[Dict]) -> Dict[str, dict]:
        """Calculate learning progress metrics"""
        progress = {}
        if not interactions:
            return progress
            
        for interaction in interactions:
            try:
                topic = interaction['topic']
                if topic not in progress:
                    progress[topic] = {
                        'correct': 0,
                        'incorrect': 0,
                        'response_times': []
                    }
                
                if interaction['is_correct']:
                    progress[topic]['correct'] += 1
                else:
                    progress[topic]['incorrect'] += 1
                    
                progress[topic]['response_times'].append(interaction['response_time'])
            except KeyError as e:
                logger.warning(f"Missing key in interaction data: {str(e)}")
                continue
        
        # Calculate averages
        for topic, data in progress.items():
            try:
                data['avg_response_time'] = statistics.mean(data['response_times']) if data['response_times'] else 0
                del data['response_times']
            except statistics.StatisticsError:
                data['avg_response_time'] = 0
                del data['response_times']
                
        return progress

    @staticmethod
    def generate_recommendations(progress: Dict) -> List[str]:
        """Generate study recommendations based on progress"""
        recommendations = []
        for topic, data in progress.items():
            try:
                total = data['correct'] + data['incorrect']
                if total == 0:
                    continue
                    
                accuracy = data['correct'] / total * 100
                if accuracy < 60:
                    recommendations.append(f"Needs review: {topic} (Accuracy: {accuracy:.1f}%)")
                elif data['avg_response_time'] < 5:
                    recommendations.append(f"Practice deeper thinking: {topic}")
            except KeyError as e:
                logger.warning(f"Missing key in progress data: {str(e)}")
                continue
        return recommendations