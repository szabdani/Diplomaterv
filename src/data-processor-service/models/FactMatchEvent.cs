using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores a sinle match event's details:
/// - General facts: match period, event second
/// - Spatial coordinates: original and destination x,y
/// - Wyscout tags, derived flags, and analytics: xG, xT
/// - Foreign key references: player, team, competition, position, event type, sub-event type
/// </summary>
[Table("fact_match_event", Schema = "dwh")]
public class FactMatchEvent
{
    [Key]
    [Column("match_event_id")]
    public long MatchEventId { get; set; }

    [Column("wy_event_id")]
    public long WyEventId { get; set; }

    [Column("match_id")]
    public int MatchId { get; set; }

    [Column("player_id")]
    public int? PlayerId { get; set; }

    [Column("team_id")]
    public int? TeamId { get; set; }

    [Column("event_type_id")]
    public short? EventTypeId { get; set; }

    [Column("sub_event_type_id")]
    public short? SubEventTypeId { get; set; }

    /// <summary>
    ///  The match period in which the event occurred
    ///  - '1H' for the first half
    ///  - '2H' for the second half
    /// </summary>
    [Column("match_period")]
    [MaxLength(4)]
    public string? MatchPeriod { get; set; }

    [Column("event_sec")]
    public float? EventSec { get; set; }

    // =====================================================================
    // Spatial coordinates, normalised to [0,100]
    // =====================================================================
    [Column("pos_orig_x")] public short? PosOrigX { get; set; }
    [Column("pos_orig_y")] public short? PosOrigY { get; set; }
    [Column("pos_dest_x")] public short? PosDestX { get; set; }
    [Column("pos_dest_y")] public short? PosDestY { get; set; }

    // =====================================================================
    // Wyscout tags, derived flags, and analytics
    // =====================================================================
    [Column("tags")]
    public int[]? Tags { get; set; }

    // Flags decoded from the tag array for querying and filtering
    [Column("is_accurate")] public bool? IsAccurate { get; set; }
    [Column("is_goal")]     public bool? IsGoal { get; set; }

    // Analytics from spatial models
    [Column("xg")] public float? Xg { get; set; }
    [Column("xt")] public float? Xt { get; set; }

    // =====================================================================
    // Foreign key references: player, team, competition, position
    // =====================================================================
    [ForeignKey(nameof(MatchId))]
    public DimMatch? Match { get; set; }

    [ForeignKey(nameof(PlayerId))]
    public DimPlayer? Player { get; set; }

    [ForeignKey(nameof(TeamId))]
    public DimTeam? Team { get; set; }

    [ForeignKey(nameof(EventTypeId))]
    public DimEventType? EventType { get; set; }

    [ForeignKey(nameof(SubEventTypeId))]
    public DimSubEventType? SubEventType { get; set; }
}
