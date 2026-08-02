from datetime import date

from fitness.models import TrainingStatus

from core.logger import logger

class FitnessAnalyzer:
    def __init__(self, intervals_client):
        self.intervals_client_instance = intervals_client

    def get_current_ftp(self, sport_type: str | None = None) -> dict:
        #logger.info("getcurrent_ftp: %s", sport_type)
        training_zones = self.intervals_client_instance.get_training_zones(sport_type)
        return dict(
            sport_type = training_zones[0].types[0],
            ftp = training_zones[0].ftp or None
        )

    def get_current_training_status(self, for_date: date) -> TrainingStatus | None:
        training_status = self.intervals_client_instance.get_current_training_status(for_date)

        if training_status is None:
            return None

        if training_status.ctl is None or training_status.atl is None:
            return training_status

        training_status.form = round(training_status.ctl - training_status.atl, 2)

        if training_status.form >= 15:
            training_status.form_status = "sehr frisch"
            training_status.summary = "Du bist aktuell sehr frisch und gut erholt. Deine kurzfristige Trainingsbelastung liegt deutlich unter deiner langfristigen Belastung."

        elif training_status.form >= 5:
            training_status.form_status = "frisch"
            training_status.summary = "Du bist aktuell gut erholt. Deine kurzfristige Trainingsbelastung liegt etwas unter deiner langfristigen Belastung."

        elif training_status.form >= -5:
            training_status.form_status = "ausgeglichen"
            training_status.summary = "Deine kurzfristige und langfristige Trainingsbelastung sind aktuell nahezu ausgeglichen."

        elif training_status.form >= -10:
            training_status.form_status = "leicht ermüdet"
            training_status.summary = "Deine kurzfristige Trainingsbelastung liegt leicht über deiner langfristigen Belastung. Eine lockere Einheit könnte sinnvoll sein."

        elif training_status.form >= -20:
            training_status.form_status = "ermüdet"
            training_status.summary = "Deine kurzfristige Trainingsbelastung liegt deutlich über deiner langfristigen Belastung. Zusätzliche intensive Einheiten solltest du gut abwägen."

        elif training_status.form >= -30:
            training_status.form_status = "stark ermüdet"
            training_status.summary = "Deine kurzfristige Trainingsbelastung ist sehr hoch. Erholung sollte momentan Priorität haben."

        else:
            training_status.form_status = "extrem ermüdet"
            training_status.summary = "Du befindest dich aktuell in einer sehr hohen Belastungsphase. Erholung ist dringend zu empfehlen."

        return training_status

