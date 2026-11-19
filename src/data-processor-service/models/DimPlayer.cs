using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores the player's source references, name, and other attributes.
/// Foreign key to the their position.
/// Foregin key to the their current team.
/// </summary>
[Table("dim_player", Schema = "dwh")]
public class DimPlayer
{
    [Key]
    [Column("player_id")]
    public int PlayerId { get; set; }

    [Column("position_id")]
    public int? PositionId { get; set; }

    [Column("current_team_id")]
    public int? CurrentTeamId { get; set; }

    [Column("wy_player_id")]
    public int? WyPlayerId { get; set; }

    [Column("tm_player_id")]
    public string? TmPlayerId { get; set; }

    /// <summary>
    /// True if the player was matched to a Capology player salary row.
    /// </summary>
    [Column("cap_matched")]
    public bool CapMatched { get; set; }

    [Column("full_name")]
    [Required]
    public string FullName { get; set; } = null!;

    [Column("short_name")]
    public string? ShortName { get; set; }

    [Column("date_of_birth")]
    public DateOnly? DateOfBirth { get; set; }

    [Column("nationality")]
    public string? Nationality { get; set; }

    /// <summary>
    /// Player's preferred foot: 'left', 'right', or 'both'.
    /// </summary>
    [Column("foot")]
    public string? Foot { get; set; }

    [Column("height_cm")]
    public int? HeightCm { get; set; }

    [ForeignKey(nameof(PositionId))]
    public DimPosition? Position { get; set; }

    [ForeignKey(nameof(CurrentTeamId))]
    public DimTeam? CurrentTeam { get; set; }
}
