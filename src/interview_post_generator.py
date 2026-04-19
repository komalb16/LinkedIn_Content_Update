#!/usr/bin/env python3
"""
interview_post_generator.py — Generate engaging interview-style LinkedIn posts

Generates posts from interview_questions.json with proper formatting,
hashtags, and structure to maximize engagement.
"""

import os
import json
import random
import hashlib
from datetime import datetime
from typing import Dict, List, Optional

try:
    from logger import get_logger
    log = get_logger("interview_posts")
except ImportError:
    class _Logger:
        def info(self, m): print(f"[INTERVIEW] {m}")
        def warning(self, m): print(f"[INTERVIEW] WARN {m}")
        def error(self, m): print(f"[INTERVIEW] ERR {m}")
    log = _Logger()

INTERVIEW_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "interview_questions.json"
)


class InterviewPostGenerator:
    """Generate interview posts from question templates."""
    
    def __init__(self, config_file: str = INTERVIEW_CONFIG_FILE):
        """Initialize generator with interview questions config."""
        self.config = self._load_config(config_file)
        self.topics = self.config.get("interview_topics", {})
        self.templates = self.config.get("interview_post_templates", {})
    
    def _load_config(self, config_file: str) -> Dict:
        """Load interview questions config."""
        if not os.path.exists(config_file):
            log.error(f"Config file not found: {config_file}")
            return {}
        
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Failed to load config: {e}")
            return {}
    
    def get_random_topic(self) -> tuple:
        """Get random topic and category."""
        if not self.topics:
            return None, None
        
        topic_key = random.choice(list(self.topics.keys()))
        topic_data = self.topics[topic_key]
        return topic_key, topic_data
    
    def get_random_question(self, topic_key: str = None) -> Optional[Dict]:
        """Get random question from specific or any topic."""
        if not topic_key:
            topic_key, _ = self.get_random_topic()
        
        if topic_key not in self.topics:
            return None
        
        questions = self.topics[topic_key].get("questions", [])
        if not questions:
            return None
        
        return random.choice(questions)
    
    def generate_opinion_poll_post(self, question: Dict) -> str:
        """Generate opinion poll-style post."""
        post = f"""I asked engineers one question:

"{question.get('question')}"

{question.get('context', '')}

The answers:
"""
        
        # Add poll options with percentages
        options = question.get("poll_options", [])
        if options:
            total = len(options)
            # Realistic distribution (not perfectly even)
            percentages = [random.randint(10, 30) for _ in range(total - 1)]
            remaining = 100 - sum(percentages)
            percentages.append(remaining)
            random.shuffle(percentages)
            
            for i, option in enumerate(options):
                pct = percentages[i]
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                post += f"\n{pct}% [{bar}]\n{option}"
        
        # Add personal take
        post += f"\n\nHere's what I think:\n[Your personal perspective]\n"
        
        # Add strong CTA
        post += f"\n\n{question.get('follow_up', '')}\n"
        
        # Add hashtags
        hashtags = " ".join(f"#{tag}" for tag in question.get("hashtags", []))
        post += f"\n\n{hashtags}"
        
        return post
    
    def generate_comparison_debate_post(self, question: Dict) -> str:
        """Generate comparison/debate-style post."""
        post = f"""{question.get('question')}

{question.get('context', '')}

Here's what I see across teams:
"""
        
        # Add comparison
        comparison = question.get("comparison", {})
        for side, details in comparison.items():
            post += f"\n\n{side}:\n"
            if isinstance(details, dict):
                for key, value in details.items():
                    post += f"• {key}: {value}\n"
            else:
                post += f"  {details}\n"
        
        post += f"\n\nMy take:\n[Your perspective]\n"
        post += f"\n\n{question.get('follow_up', '')}\n"
        
        hashtags = " ".join(f"#{tag}" for tag in question.get("hashtags", []))
        post += f"\n\n{hashtags}"
        
        return post
    
    def generate_lessons_learned_post(self, question: Dict) -> str:
        """Generate lessons learned story-style post."""
        post = f"""{question.get('question')}

{question.get('context', '')}

Here's what happened:

[PROBLEM]
[STRUGGLE]
[THE MOMENT IT CLICKED]
[WHAT I DID]
[RESULT]

The lesson:
[Key insight]
"""
        
        post += f"\n\n{question.get('follow_up', '')}\n"
        
        hashtags = " ".join(f"#{tag}" for tag in question.get("hashtags", []))
        post += f"\n\n{hashtags}"
        
        return post
    
    def generate_expert_question_post(self, question: Dict) -> str:
        """Generate expert Q&A style post."""
        post = f"""{question.get('question')}

{question.get('context', '')}

Different approaches I've seen:
"""
        
        tactics = question.get("tactics", question.get("perspectives", question.get("options", [])))
        for i, tactic in enumerate(tactics, 1):
            post += f"\n{i}. {tactic}"
        
        post += f"\n\nWhat I use:\n[Your approach]\n\nWhy:\n[Your reasoning]\n"
        post += f"\n\n{question.get('follow_up', '')}\n"
        
        hashtags = " ".join(f"#{tag}" for tag in question.get("hashtags", []))
        post += f"\n\n{hashtags}"
        
        return post
    
    def generate_post_from_question(self, question: Dict = None, question_id: str = None) -> Optional[str]:
        """Generate complete post from question."""
        if not question and question_id:
            question = self._find_question_by_id(question_id)
        
        if not question:
            question = self.get_random_question()
        
        if not question:
            log.error("No question available")
            return None
        
        question_type = question.get("type", "opinion_poll")
        
        try:
            if question_type == "opinion_poll":
                return self.generate_opinion_poll_post(question)
            elif question_type in ["comparison_debate", "yes_no_debate"]:
                return self.generate_comparison_debate_post(question)
            elif question_type in ["lessons_learned", "horror_story", "failure_story", "journey_narrative"]:
                return self.generate_lessons_learned_post(question)
            else:  # expert_question, problem_solution, etc.
                return self.generate_expert_question_post(question)
        except Exception as e:
            log.error(f"Failed to generate post: {e}")
            return None
    
    def _find_question_by_id(self, question_id: str) -> Optional[Dict]:
        """Find question by ID across all topics."""
        for topic_data in self.topics.values():
            questions = topic_data.get("questions", [])
            for q in questions:
                if q.get("id") == question_id:
                    return q
        return None
    
    def get_topic_questions(self, topic: str) -> List[Dict]:
        """Get all questions for a topic."""
        if topic not in self.topics:
            return []
        return self.topics[topic].get("questions", [])
    
    def get_all_topics(self) -> List[str]:
        """Get all available topics."""
        return list(self.topics.keys())
    
    def get_engagement_level(self, topic: str) -> str:
        """Get expected engagement level for topic."""
        if topic in self.topics:
            return self.topics[topic].get("engagement_level", "medium")
        return "unknown"
    
    def get_best_diagram_styles(self, topic: str) -> List[int]:
        """Get recommended diagram styles for topic."""
        if topic in self.topics:
            return self.topics[topic].get("best_diagram_styles", [7])
        return [7]  # Default to Card Grid
    
    def rotate_through_topics(self, num_posts: int = 7) -> List[Dict]:
        """Generate rotation of posts through all topics (weekly rotation)."""
        topics = self.get_all_topics()
        posts = []
        
        for i in range(num_posts):
            topic = topics[i % len(topics)]
            question = self.get_random_question(topic)
            
            if question:
                post_data = {
                    "topic": topic,
                    "question_id": question.get("id"),
                    "post": self.generate_post_from_question(question),
                    "diagram_styles": self.get_best_diagram_styles(topic),
                    "expected_engagement": self.templates.get(
                        question.get("type", "opinion_poll"),
                        {}
                    ).get("expected_engagement", "200-350 comments")
                }
                posts.append(post_data)
        
        return posts


# ═════════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*70)
    print("INTERVIEW POST GENERATOR - Examples")
    print("="*70 + "\n")
    
    gen = InterviewPostGenerator()
    
    # Show available topics
    topics = gen.get_all_topics()
    print(f"Available topics ({len(topics)}):")
    for topic in topics:
        print(f"  ✓ {topic}")
    
    # Generate sample posts from each topic
    print("\n" + "="*70)
    print("SAMPLE POSTS FROM EACH TOPIC")
    print("="*70 + "\n")
    
    for topic in topics:
        question = gen.get_random_question(topic)
        if question:
            print(f"\n{'─'*70}")
            print(f"TOPIC: {topic.upper()}")
            print(f"QUESTION: {question.get('question')}")
            print(f"TYPE: {question.get('type')}")
            print(f"EXPECTED ENGAGEMENT: {question.get('difficulty')}")
            print(f"{'─'*70}")
            
            post = gen.generate_post_from_question(question)
            if post:
                print(post[:300] + "...\n")
    
    # Generate weekly rotation
    print("\n" + "="*70)
    print("WEEKLY POST ROTATION")
    print("="*70 + "\n")
    
    weekly = gen.rotate_through_topics(7)
    for i, post_data in enumerate(weekly, 1):
        print(f"\nPost {i} - {post_data['topic'].upper()}")
        print(f"Question ID: {post_data['question_id']}")
        print(f"Expected Engagement: {post_data['expected_engagement']}")
        print(f"Best Diagram Styles: {post_data['diagram_styles']}")
