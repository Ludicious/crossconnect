from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

# Keys used by the application — documented here for discoverability:
#   cable_slack_inches_per_end    default "18"
#   cable_standard_lengths_m      default "0.5,1,2,3,5,7,10"
#   max_rack_ru                   default "54"


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
