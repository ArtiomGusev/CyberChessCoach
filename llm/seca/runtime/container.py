from llm.seca.storage.event_store import EventStore
from llm.seca.skill.pipeline import SkillPipeline
from llm.seca.world_model.safe_stub import SafeWorldModel
from llm.seca.curriculum.policy import CurriculumPolicy
from llm.seca.coaching.coach_engine import CoachEngine
from llm.seca.realtime.live_coach import LiveCoach
from llm.seca.engines.adaptive.controller import AdaptiveOpponent


class Runtime:
    def __init__(self):
        self.event_store = EventStore("data/events.db")
        self.skill_pipeline = SkillPipeline(self.event_store)
        self.world_model = SafeWorldModel()
        self.curriculum_policy = CurriculumPolicy(self.world_model)

        self.coach_engine = CoachEngine(
            self.skill_pipeline,
            self.curriculum_policy,
            self.world_model,
        )

        self.opponent = AdaptiveOpponent()

        self.live_coach = LiveCoach(
            move_analyzer=None,  # wired later
            skill_updater=self.skill_pipeline,
            hint_policy=None,
            tone_adapter=None,
            opponent_controller=self.opponent,
            coach_llm=self.coach_engine,
        )
