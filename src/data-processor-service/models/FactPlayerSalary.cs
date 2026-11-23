using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores a player's salary information: player, team, season, and wage details.
/// Foreign key to the player.
/// </summary>
[Table("fact_player_salary", Schema = "dwh")]
public class FactPlayerSalary
{
    [Key]
    [Column("salary_id")]
    public long SalaryId { get; set; }

    [Column("player_id")]
    public int PlayerId { get; set; }

    [Column("team_id")]
    public int? TeamId { get; set; }

    [Column("season_label")]
    [Required]
    public string SeasonLabel { get; set; } = "2017-2018";

    [Column("weekly_wage_eur")]
    public decimal? WeeklyWageEur { get; set; }

    [Column("annual_wage_eur")]
    public decimal? AnnualWageEur { get; set; }

    /// <summary>
    /// The currency of the original wage data ('GBP' or 'EUR' before conversion).
    /// </summary>
    [Column("source_currency")]
    [MaxLength(3)]
    public string? SourceCurrency { get; set; }

    [ForeignKey(nameof(PlayerId))]
    public DimPlayer? Player { get; set; }

    [ForeignKey(nameof(TeamId))]
    public DimTeam? Team { get; set; }
}
