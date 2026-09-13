# https://app.eraser.io/workspace/zyjpVPN1yASJE0esOk0H
"""
SpectraSoft — Database Models
"""

from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.sql import func
from core.database import Base


class AnalyticalGroup(Base):
    __tablename__ = "analytical_groups"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(100), nullable=False, unique=True, index=True)
    display_order = Column(Integer, default=0)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    page_01_source         = Column(JSON, default=dict)
    page_02_attenuator     = Column(JSON, default=dict)
    page_03_channel        = Column(JSON, default=dict)
    page_04_drift          = Column(JSON, default=dict)
    page_05_wc             = Column(JSON, default=dict)
    page_06_matrix         = Column(JSON, default=dict)
    page_07_master         = Column(JSON, default=dict)
    page_08_display        = Column(JSON, default=dict)
    page_09_purity         = Column(JSON, default=dict)

    def __repr__(self):
        return f"<AnalyticalGroup(id={self.id}, name='{self.name}')>"

    def to_dict(self):
        return {
            "id":            self.id,
            "name":          self.name,
            "display_order": self.display_order,
        }


class SourceCode(Base):
    """
    16 fixed rows (entry_no 0-15).
    entry_no is the hardware command value sent over UART.
    name is user-editable label shown in dropdowns.
    """
    __tablename__ = "source_codes"

    entry_no = Column(Integer, primary_key=True)  # 0-15, no autoincrement
    name     = Column(String(100), default="")

    def __repr__(self):
        return f"<SourceCode(entry_no={self.entry_no}, name='{self.name}')>"
    
class MasterElement(Base):
    """
    Master list of all elements the spectrometer supports.
    Users can add/edit/remove entries from the Settings page.
    Page 02 (Attenuator) and other pages pull from this table.

    itg_no is the primary key (hardware channel identifier).
    """
    __tablename__ = "master_elements"

    itg_no = Column(Integer, primary_key=True)           # primary key, user‑defined
    ele_name = Column(String(20), nullable=False)        # e.g., "FE"
    wavelength = Column(String(20), default="")          # e.g., "271.4"

    def __repr__(self):
        return f"<MasterElement(itg_no={self.itg_no}, ele_name='{self.ele_name}')>"