class Terminal(Base):
    __tablename__ = "terminals"

    id = Column(String(50), primary_key=True)
    organization_id = Column(String(50), ForeignKey("organizations.id"))
    terminal_group_id = Column(String(50), ForeignKey("terminal_groups.id"))

    name = Column(String(255))
    address = Column(String(255))
    time_zone = Column(String(20))

    organization = relationship("Organization", back_populates="terminals")
    terminal_group = relationship("TerminalGroup", back_populates="terminals")
