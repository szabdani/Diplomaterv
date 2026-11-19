using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores the teams's source references, name and country.
/// Foreign key to the competition the team participates in.
/// </summary>
[Table("dim_team", Schema = "dwh")]
public class DimTeam
{
    [Key]
    [Column("team_id")]
    public int TeamId { get; set; }

    [Column("competition_id")]
    public int? CompetitionId { get; set; }

    [Column("wy_team_id")]
    public int? WyTeamId { get; set; }

    [Column("tm_club_id")]
    public string? TmClubId { get; set; }
    
    [Column("cap_club_slug")]
    public string? CapClubSlug { get; set; }

    [Column("official_name")]
    [Required]
    public string OfficialName { get; set; } = null!;

    [Column("short_name")]
    public string? ShortName { get; set; }

    [ForeignKey(nameof(CompetitionId))]
    public DimCompetition? Competition { get; set; }

    public ICollection<DimPlayer> Players { get; set; } = new List<DimPlayer>();
    public ICollection<DimMatch> Matches { get; set; } = new List<DimMatch>();
}
