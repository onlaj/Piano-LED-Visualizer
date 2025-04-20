import time
import math

class ScoreManager:
    def __init__(self):
        self.reset()
        
        # Default scoring parameters
        self.base_score = 200
        self.max_delay = 2.0  # 2 seconds
        self.penalty = 50
        
    def reset(self):
        """Reset score and combo at the start of a learning session"""
        self.score = 0
        self.combo = 0
        self.last_score_update = 0
    
    def get_score_multiplier(self):
        """Get multiplier based on combo tier"""
        if self.combo < 10:
            return 1
        elif self.combo < 20:
            return 2
        elif self.combo < 30:
            return 3
        elif self.combo < 40:
            return 4
        else:
            return 5
    
    def calculate_score_for_correct_note(self, delay):
        """Calculate score increment for a correctly pressed note"""
        abs_delay = abs(delay)
        
        # If delay is too large, no points and reset combo
        if abs_delay >= self.max_delay:
            self.combo = 0
            return 0
        
        # Calculate score using formula: ScoreMultiplier * baseScore * ((maxDelay - abs(delay)) / maxDelay)^2
        multiplier = self.get_score_multiplier()
        score_increment = multiplier * self.base_score * pow((self.max_delay - abs_delay) / self.max_delay, 2)
        
        # Increment combo
        self.combo += 1
        
        
        # Round to nearest integer
        return round(score_increment)
    
    def add_score_for_correct_note(self, delay):
        """Add score for a correctly pressed note"""
        score_increment = self.calculate_score_for_correct_note(delay)
        self.score += score_increment
        self.last_score_update = score_increment
        return score_increment
    
    def penalize_for_wrong_note(self):
        """Subtract points and reset combo for a wrong note"""
        self.score = max(0, self.score - self.penalty)
        self.combo = 0
        self.last_score_update = -self.penalty
        return -self.penalty
    
    def get_score(self):
        """Get current score"""
        return self.score
    
    def get_combo(self):
        """Get current combo"""
        return self.combo
    
    def get_multiplier(self):
        """Get current multiplier"""
        return self.get_score_multiplier()
    
    def get_last_score_update(self):
        """Get last score change (positive for correct notes, negative for mistakes)"""
        return self.last_score_update 