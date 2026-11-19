using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores a player's injury information: type, duration, and missed days/games.
/// Foreign key to the player.
/// </summary>
[Table("fact_injury", Schema = "dwh")]
public class FactInjury
{
    [Key]
    [Column("injury_id")]
    public long InjuryId { get; set; }

    [Column("player_id")]
    public int PlayerId { get; set; }

    [Column("injury_type")]
    public string? InjuryType { get; set; }

    [Column("from_date")]
    public DateOnly? FromDate { get; set; }

    [Column("until_date")]
    public DateOnly? UntilDate { get; set; }

    [Column("days_out")]
    public int? DaysOut { get; set; }

    [Column("games_missed")]
    public int? GamesMissed { get; set; }

    [ForeignKey(nameof(PlayerId))]
    public DimPlayer Player { get; set; }
}
