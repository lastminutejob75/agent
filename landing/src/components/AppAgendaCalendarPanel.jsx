import { Fragment } from "react";
import { CalendarDays, Check, ChevronLeft, ChevronRight, Clock3, Plus } from "lucide-react";

export default function AppAgendaCalendarPanel({
  styles: S,
  totalAppointments,
  doneAppointments,
  upcomingAppointments,
  isConnected,
  error,
  draggedAppointment,
  viewMode,
  actionMessage,
  selectedAppointment,
  search,
  statusFilter,
  getFilterLabel,
  setSearch,
  setStatusFilter,
  scrollToSetup,
  navigate,
  navigatePrevious,
  navigateNext,
  currentTitle,
  currentPanelTitle,
  setSelectedDate,
  setViewMode,
  todayIso,
  timelineHours,
  appointmentsByCell,
  selectedDate,
  currentHourLabel,
  dragOverCellKey,
  handleCellDragOver,
  handleCellDragLeave,
  handleCellDrop,
  handleAppointmentDragStart,
  handleAppointmentDragEnd,
  setSelectedAppointment,
  setHoveredAppointment,
  setHoveredRect,
  getStatusConfigByKey,
  getViewStatusKey,
  getTypeIcon,
  addMinutesToTimeLabel,
  currentMinuteOffset,
  now,
  selectedDayAppointments,
  buildMonthGrid,
  agendaByDate,
  isSameMonth,
  formatDayNumber,
  handleMonthCellDragOver,
  handleMonthCellDragLeave,
  handleMonthCellDrop,
  weekDates,
  formatWeekdayLabel,
  emptyTimeline,
}) {
  return (
    <>
      <div style={S.header}>
        <div>
          <h1 style={S.title}>Agenda</h1>
          <p style={S.subtitle}>Gérez vos rendez-vous et appels planifiés</p>
        </div>
        <button type="button" onClick={scrollToSetup} style={S.primaryButton}>
          <Plus size={16} strokeWidth={2.4} />
          <span>Nouveau rendez-vous</span>
        </button>
      </div>

      <div className="agenda-page-stats" style={S.statsGrid}>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>Total rendez-vous</div>
            <div style={S.statValue}>{totalAppointments}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #3b82f6, #2563eb)" }}>
            <CalendarDays size={16} strokeWidth={2.2} />
          </div>
        </div>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>Confirmés</div>
            <div style={{ ...S.statValue, color: "#10b981" }}>{doneAppointments}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #10b981, #059669)" }}>
            <Check size={16} strokeWidth={2.4} />
          </div>
        </div>
        <div style={S.statCard}>
          <div>
            <div style={S.statLabel}>En attente</div>
            <div style={{ ...S.statValue, color: "#f59e0b" }}>{upcomingAppointments}</div>
          </div>
          <div style={{ ...S.statIcon, background: "linear-gradient(135deg, #f59e0b, #d97706)" }}>
            <Clock3 size={16} strokeWidth={2.2} />
          </div>
        </div>
      </div>

      {!isConnected ? (
        <div style={S.notice}>
          <div>
            <div style={S.noticeTitle}>Agenda UWI déjà actif</div>
            <div style={S.noticeText}>
              Même sans agenda Google connecté, cette vue affiche les rendez-vous pris par l'assistant dans le calendrier UWI.
            </div>
          </div>
          <button type="button" onClick={scrollToSetup} style={S.noticeButton}>
            Finaliser la connexion
          </button>
        </div>
      ) : (
        <div style={{ ...S.notice, borderColor: "#bfdbfe", background: "#eff6ff" }}>
          <div>
            <div style={S.noticeTitle}>Agenda externe connecté</div>
            <div style={S.noticeText}>
              Google Calendar est bien relié. Les rendez-vous du jour remontent ici automatiquement.
            </div>
          </div>
          <div style={S.connectedBadge}>Google actif</div>
        </div>
      )}

      {error ? <div style={S.errorBox}>Erreur: {error}</div> : null}
      {draggedAppointment ? (
        <div style={S.dragHintBar}>
          Déplacement de <b>{draggedAppointment.patient || "ce rendez-vous"}</b>
          {viewMode === "month" ? " : déposez sur un jour pour ouvrir son planning." : " : déposez sur une case horaire libre."}
        </div>
      ) : null}
      {actionMessage && !selectedAppointment ? <div style={S.actionToast}>{actionMessage}</div> : null}

      {(search || statusFilter !== "all") ? (
        <div style={S.activeFilterBar}>
          <div style={S.activeFilterText}>
            Filtre actif
            {statusFilter !== "all" ? ` · ${getFilterLabel(statusFilter)}` : ""}
            {search ? ` · "${search}"` : ""}
          </div>
          <button
            type="button"
            onClick={() => {
              setSearch("");
              setStatusFilter("all");
            }}
            style={S.clearFilterButton}
          >
            Réinitialiser
          </button>
        </div>
      ) : null}

      <div style={S.panel}>
        <div style={S.calendarTopBar}>
          <button type="button" onClick={navigatePrevious} style={S.navButton}>
            <ChevronLeft size={18} strokeWidth={2.2} />
          </button>
          <div style={S.calendarTopCenter}>
            <div style={S.dateTitle}>{currentTitle}</div>
            <div style={S.viewSwitch}>
              <button type="button" onClick={() => setSelectedDate(todayIso)} style={S.viewSwitchGhost}>
                Aujourd'hui
              </button>
              <button type="button" onClick={() => setViewMode("month")} style={viewMode === "month" ? S.viewSwitchActive : S.viewSwitchGhost}>
                Mois
              </button>
              <button type="button" onClick={() => setViewMode("week")} style={viewMode === "week" ? S.viewSwitchActive : S.viewSwitchGhost}>
                Semaine
              </button>
              <button type="button" onClick={() => setViewMode("day")} style={viewMode === "day" ? S.viewSwitchActive : S.viewSwitchGhost}>
                Jour
              </button>
            </div>
          </div>
          <button type="button" onClick={navigateNext} style={S.navButton}>
            <ChevronRight size={18} strokeWidth={2.2} />
          </button>
        </div>

        <div style={S.calendarPanelHeader}>
          <div style={S.panelTitle}>{currentPanelTitle}</div>
        </div>

        {timelineHours.length > 0 ? (
          viewMode === "day" ? (
            <div className="agenda-day-layout" style={S.dayLayout}>
              <div style={S.dayMain}>
                <div style={S.daySummaryBar}>
                  <div>
                    <div style={S.daySummaryTitle}>Planning de la journée</div>
                    <div style={S.daySummaryText}>{selectedDayAppointments.length} rendez-vous prévus</div>
                  </div>
                </div>
                <div style={S.dayTimeline}>
                  {timelineHours.map((hour) => {
                    const items = appointmentsByCell[`${selectedDate}-${hour}`] || [];
                    return (
                      <div key={hour} style={S.dayRow}>
                        <div style={{ ...S.dayHour, ...(selectedDate === todayIso && hour === currentHourLabel ? S.dayHourNow : null) }}>{hour}</div>
                        <div
                          style={{
                            ...S.dayCell,
                            ...(selectedDate === todayIso && hour === currentHourLabel ? S.dayCellNow : null),
                            ...(dragOverCellKey === `${selectedDate}-${hour}` ? S.dropCellActive : null),
                          }}
                          onDragOver={(event) => handleCellDragOver(event, selectedDate, hour)}
                          onDragLeave={() => handleCellDragLeave(selectedDate, hour)}
                          onDrop={(event) => handleCellDrop(event, selectedDate, hour)}
                        >
                          <div style={S.dayHalfLine} />
                          {items.length > 0
                            ? items.map((appointment) => {
                                const visualStatus = getStatusConfigByKey(getViewStatusKey(appointment));
                                return (
                                  <button
                                    key={appointment.id}
                                    className="agenda-day-appointment"
                                    type="button"
                                    draggable={appointment.canReschedule}
                                    onClick={() => setSelectedAppointment(appointment)}
                                    onDragStart={(event) => handleAppointmentDragStart(event, appointment)}
                                    onDragEnd={handleAppointmentDragEnd}
                                    onMouseEnter={(event) => {
                                      setHoveredAppointment(appointment);
                                      setHoveredRect(event.currentTarget.getBoundingClientRect());
                                    }}
                                    onMouseLeave={() => {
                                      setHoveredAppointment(null);
                                      setHoveredRect(null);
                                    }}
                                    style={{
                                      ...S.dayAppointmentCard,
                                      ...(draggedAppointment?.id === appointment.id ? S.draggingAppointmentCard : null),
                                      borderColor: visualStatus.border,
                                      background: visualStatus.grad || visualStatus.light,
                                    }}
                                  >
                                    <div style={S.dayAppointmentTop}>
                                      <div>
                                        <div style={{ ...S.appointmentTime, color: visualStatus.grad ? "rgba(255,255,255,.92)" : "#0f766e" }}>
                                          {appointment.displayTime}
                                        </div>
                                        <div style={S.appointmentIdentityRow}>
                                          {appointment.source === "UWI" ? (
                                            <span
                                              style={{
                                                ...S.aiInlineBadge,
                                                background: visualStatus.grad ? "rgba(255,255,255,.18)" : "#ede9fe",
                                                color: visualStatus.grad ? "#fff" : "#7c3aed",
                                                borderColor: visualStatus.grad ? "rgba(255,255,255,.25)" : "#ddd6fe",
                                              }}
                                            >
                                              IA
                                            </span>
                                          ) : null}
                                          <div style={{ ...S.weekAppointmentName, color: visualStatus.grad ? "#fff" : "#111827" }}>
                                            {appointment.patient || "Patient"}
                                          </div>
                                        </div>
                                        <div style={{ ...S.weekAppointmentType, color: visualStatus.grad ? "rgba(255,255,255,.82)" : "#4b5563" }}>
                                          {getTypeIcon(appointment.type)} {appointment.type || "Consultation"}
                                        </div>
                                      </div>
                                      <span
                                        style={{
                                          ...S.statusBadge,
                                          background: visualStatus.grad ? "rgba(255,255,255,.18)" : visualStatus.light,
                                          color: visualStatus.grad ? "#fff" : visualStatus.color,
                                          borderColor: visualStatus.grad ? "rgba(255,255,255,.25)" : visualStatus.border,
                                        }}
                                      >
                                        {visualStatus.label}
                                      </span>
                                    </div>
                                    <div style={S.weekAppointmentPills}>
                                      <span
                                        style={{
                                          ...S.sourceBadge,
                                          background: appointment.source === "UWI" ? (visualStatus.grad ? "rgba(255,255,255,.2)" : "#ede9fe") : (visualStatus.grad ? "rgba(255,255,255,.16)" : "#eef2ff"),
                                          color: visualStatus.grad ? "#fff" : appointment.source === "UWI" ? "#7c3aed" : "#4f46e5",
                                          borderColor: visualStatus.grad ? "rgba(255,255,255,.28)" : appointment.source === "UWI" ? "#ddd6fe" : "#c7d2fe",
                                        }}
                                      >
                                        {appointment.source === "UWI" ? "Réservé par UWI" : "Agenda connecté"}
                                      </span>
                                    </div>
                                    <div style={{ ...S.appointmentRange, color: visualStatus.grad ? "rgba(255,255,255,.86)" : "#475569" }}>
                                      {appointment.displayTime} - {addMinutesToTimeLabel(appointment.displayTime, appointment.duration)}
                                    </div>
                                    <div style={{ ...S.weekAppointmentMeta, color: visualStatus.grad ? "rgba(255,255,255,.76)" : "#6b7280" }}>
                                      <span>{appointment.duration} min</span>
                                      <span>{appointment.sourceLabel}</span>
                                    </div>
                                  </button>
                                );
                              })
                            : <div style={S.dayEmptyCell} />}
                          {selectedDate === todayIso && hour === currentHourLabel ? (
                            <div style={{ ...S.nowLine, top: `${currentMinuteOffset}%` }}>
                              <span style={S.nowDot} />
                              <span style={S.nowLabel}>{now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</span>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div style={S.daySidebar}>
                <div style={S.sideCard}>
                  <div style={S.sideCardTitle}>Détails</div>
                  {selectedAppointment && selectedAppointment.date === selectedDate ? (
                    <div style={S.sideDetailBody}>
                      <div style={S.sideDetailName}>{selectedAppointment.patient || "Patient"}</div>
                      <div style={S.sideDetailText}>{selectedAppointment.type || "Consultation"}</div>
                      <div style={S.sideDetailText}>{selectedAppointment.displayTime || "—"} · {selectedAppointment.duration || "—"} min</div>
                      <div style={S.sideDetailText}>{selectedAppointment.sourceLabel || "UWI"}</div>
                    </div>
                  ) : (
                    <div style={S.sideEmpty}>Sélectionnez un rendez-vous pour voir les détails</div>
                  )}
                </div>
                <div style={{ ...S.sideCard, ...S.quickActionsCard }}>
                  <div style={S.sideCardTitle}>Actions rapides</div>
                  <button type="button" onClick={scrollToSetup} style={S.quickActionButton}>+ Nouveau RDV</button>
                  <button type="button" onClick={() => navigate("/app/appels")} style={S.quickActionButton}>Ouvrir appels</button>
                  <button type="button" onClick={() => navigate("/app/horaires")} style={S.quickActionButton}>Modifier horaires</button>
                </div>
              </div>
            </div>
          ) : viewMode === "month" ? (
            <div style={S.monthWrap}>
              <div className="agenda-month-grid" style={S.monthGrid}>
                {["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"].map((label) => (
                  <div key={label} style={S.monthWeekday}>{label}</div>
                ))}
                {buildMonthGrid(selectedDate).map((date) => {
                  const items = agendaByDate?.[date]?.slots || [];
                  const inCurrentMonth = isSameMonth(date, selectedDate);
                  return (
                    <button
                      key={date}
                      type="button"
                      onClick={() => {
                        setSelectedDate(date);
                        setViewMode("day");
                      }}
                      onDragOver={(event) => handleMonthCellDragOver(event, date)}
                      onDragLeave={() => handleMonthCellDragLeave(date)}
                      onDrop={(event) => handleMonthCellDrop(event, date)}
                      style={{
                        ...S.monthCell,
                        ...(date === selectedDate ? S.monthCellActive : null),
                        ...(inCurrentMonth ? null : S.monthCellMuted),
                        ...(dragOverCellKey === `month-${date}` ? S.monthCellDropActive : null),
                      }}
                    >
                      <div style={S.monthCellDate}>{formatDayNumber(date)}</div>
                      {items.length > 0 ? (
                        <div style={S.monthDotWrap}>
                          <span style={S.monthDot}>{items.length}</span>
                        </div>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            <div style={S.weekCalendarWrap}>
              <div className="agenda-week-calendar" style={S.weekCalendar}>
                <div style={S.weekCorner} />
                {weekDates.map((date) => (
                  <button
                    key={date}
                    type="button"
                    onClick={() => setSelectedDate(date)}
                    style={{
                      ...S.weekDayHeader,
                      ...(date === selectedDate ? S.weekDayHeaderActive : null),
                      ...(date === todayIso ? S.weekDayHeaderToday : null),
                    }}
                  >
                    <span style={S.weekDayLabel}>{formatWeekdayLabel(date)}</span>
                    <span style={S.weekDayNumber}>{formatDayNumber(date)}</span>
                    {date === todayIso ? <span style={S.todayPill}>Aujourd'hui</span> : null}
                  </button>
                ))}

                {timelineHours.map((hour) => (
                  <Fragment key={hour}>
                    <div style={S.timeCell}>
                      <div style={S.timeHourLabel}>{hour}</div>
                      <div style={S.timeHalfLabel}>{hour.slice(0, 2)}:30</div>
                    </div>
                    {weekDates.map((date) => {
                      const items = appointmentsByCell[`${date}-${hour}`] || [];
                      const isTodayColumn = date === todayIso;
                      return (
                        <div
                          key={`${date}-${hour}`}
                          style={{
                            ...S.weekCell,
                            ...(date === selectedDate ? S.weekCellActive : null),
                            ...(isTodayColumn ? S.weekCellToday : null),
                            ...(isTodayColumn && hour === currentHourLabel ? S.weekCellNow : null),
                            ...(dragOverCellKey === `${date}-${hour}` ? S.dropCellActive : null),
                          }}
                          onDragOver={(event) => handleCellDragOver(event, date, hour)}
                          onDragLeave={() => handleCellDragLeave(date, hour)}
                          onDrop={(event) => handleCellDrop(event, date, hour)}
                        >
                          <div style={S.weekHalfLine} />
                          {items.length > 0
                            ? items.map((appointment) => {
                                const visualStatus = getStatusConfigByKey(getViewStatusKey(appointment));
                                return (
                                  <button
                                    key={appointment.id}
                                    className="agenda-week-appointment"
                                    type="button"
                                    draggable={appointment.canReschedule}
                                    onClick={() => setSelectedAppointment(appointment)}
                                    onDragStart={(event) => handleAppointmentDragStart(event, appointment)}
                                    onDragEnd={handleAppointmentDragEnd}
                                    onMouseEnter={(event) => {
                                      setHoveredAppointment(appointment);
                                      setHoveredRect(event.currentTarget.getBoundingClientRect());
                                    }}
                                    onMouseLeave={() => {
                                      setHoveredAppointment(null);
                                      setHoveredRect(null);
                                    }}
                                    style={{
                                      ...S.weekAppointmentCard,
                                      ...(draggedAppointment?.id === appointment.id ? S.draggingAppointmentCard : null),
                                      borderColor: visualStatus.border,
                                      background: visualStatus.grad || visualStatus.light,
                                    }}
                                  >
                                    <div style={S.weekAppointmentTop}>
                                      <div>
                                        <div style={{ ...S.appointmentTime, color: visualStatus.grad ? "rgba(255,255,255,.92)" : "#0f766e" }}>
                                          {appointment.displayTime}
                                        </div>
                                        <div style={S.appointmentIdentityRow}>
                                          {appointment.source === "UWI" ? (
                                            <span
                                              style={{
                                                ...S.aiInlineBadge,
                                                background: visualStatus.grad ? "rgba(255,255,255,.18)" : "#ede9fe",
                                                color: visualStatus.grad ? "#fff" : "#7c3aed",
                                                borderColor: visualStatus.grad ? "rgba(255,255,255,.25)" : "#ddd6fe",
                                              }}
                                            >
                                              IA
                                            </span>
                                          ) : null}
                                          <div style={{ ...S.weekAppointmentName, color: visualStatus.grad ? "#fff" : "#111827" }}>
                                            {appointment.patient || "Patient"}
                                          </div>
                                        </div>
                                      </div>
                                      <span
                                        style={{
                                          ...S.statusBadge,
                                          background: visualStatus.grad ? "rgba(255,255,255,.18)" : visualStatus.light,
                                          color: visualStatus.grad ? "#fff" : visualStatus.color,
                                          borderColor: visualStatus.grad ? "rgba(255,255,255,.25)" : visualStatus.border,
                                        }}
                                      >
                                        {visualStatus.label}
                                      </span>
                                    </div>
                                    <div style={{ ...S.weekAppointmentType, color: visualStatus.grad ? "rgba(255,255,255,.82)" : "#4b5563" }}>
                                      {getTypeIcon(appointment.type)} {appointment.type || "Consultation"}
                                    </div>
                                    <div style={S.weekAppointmentPills}>
                                      <span
                                        style={{
                                          ...S.sourceBadge,
                                          background: appointment.source === "UWI" ? (visualStatus.grad ? "rgba(255,255,255,.2)" : "#ede9fe") : (visualStatus.grad ? "rgba(255,255,255,.16)" : "#eef2ff"),
                                          color: visualStatus.grad ? "#fff" : appointment.source === "UWI" ? "#7c3aed" : "#4f46e5",
                                          borderColor: visualStatus.grad ? "rgba(255,255,255,.28)" : appointment.source === "UWI" ? "#ddd6fe" : "#c7d2fe",
                                        }}
                                      >
                                        {appointment.source === "UWI" ? "Réservé par UWI" : "Agenda connecté"}
                                      </span>
                                    </div>
                                    <div style={{ ...S.appointmentRange, color: visualStatus.grad ? "rgba(255,255,255,.86)" : "#475569" }}>
                                      {appointment.displayTime} - {addMinutesToTimeLabel(appointment.displayTime, appointment.duration)}
                                    </div>
                                    <div style={{ ...S.weekAppointmentMeta, color: visualStatus.grad ? "rgba(255,255,255,.76)" : "#6b7280" }}>
                                      <span>{appointment.sourceLabel}</span>
                                      <span>{appointment.duration} min</span>
                                    </div>
                                  </button>
                                );
                              })
                            : null}
                          {isTodayColumn && hour === currentHourLabel ? (
                            <div style={{ ...S.nowLine, top: `${currentMinuteOffset}%` }}>
                              <span style={S.nowDot} />
                              <span style={S.nowLabel}>{now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</span>
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </Fragment>
                ))}
              </div>
            </div>
          )
        ) : emptyTimeline.closed ? (
          <div style={S.emptyState}>
            <div style={S.emptyTitle}>Cabinet fermé ce jour</div>
            <div style={S.emptyText}>Aucun créneau prévu selon vos horaires actuels.</div>
            <button type="button" onClick={() => navigate("/app/horaires")} style={S.secondaryButton}>
              Modifier mes horaires
            </button>
          </div>
        ) : (
          <div style={S.emptyState}>
            <div style={S.emptyTitle}>Aucun horaire configuré</div>
            <div style={S.emptyText}>Définissez vos horaires pour afficher un agenda exploitable par l'assistant.</div>
            <button type="button" onClick={() => navigate("/app/horaires")} style={S.secondaryButton}>
              Configurer mes horaires
            </button>
          </div>
        )}
      </div>
    </>
  );
}
