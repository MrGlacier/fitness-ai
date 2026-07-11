from core.logger import logger

class FitnessAnalyzer:
    def __init__(self, intervals_client):
        self.intervals_client_instance = intervals_client

    def get_current_ftp(self, sport_type: str | None = None) -> dict:
        logger.info("getcurrent_ftp: %s", sport_type)
        training_zones = self.intervals_client_instance.get_training_zones(sport_type)
        return dict(
            sport_type = training_zones[0].types[0],
            ftp = training_zones[0].ftp or None
        )
