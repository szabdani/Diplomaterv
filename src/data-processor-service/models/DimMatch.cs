using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores the matches's wyscout reference, match date and score.
/// Foreign key to the competition the match takes place in.
/// Foregin key to the home and away teams.
/// </summary>
[Table("dim_match", Schema = "dwh")]
public class DimMatch
{
    [Key]
    [Column("match_id")]
    public int MatchId { get; set; }

    [Column("competition_id")]
    public int? CompetitionId { get; set; }

    [Column("home_team_id")]
    public int? HomeTeamId { get; set; }

    [Column("away_team_id")]
    public int? AwayTeamId { get; set; }

    [Column("wy_match_id")]
    public int? WyMatchId { get; set; }

    [Column("match_date")]
    public DateOnly? MatchDate { get; set; }

    [Column("gameweek")]
    public int? Gameweek { get; set; }

    [Column("home_score")]
    public short? HomeScore { get; set; }

    [Column("away_score")]
    public short? AwayScore { get; set; }

    [ForeignKey(nameof(CompetitionId))]
    public DimCompetition? Competition { get; set; }

    [ForeignKey(nameof(HomeTeamId))]
    public DimTeam? HomeTeam { get; set; }

    [ForeignKey(nameof(AwayTeamId))]
    public DimTeam? AwayTeam { get; set; }
    
    public ICollection<FactMatchEvent> MatchEvents { get; set; } = new List<FactMatchEvent>();
}
