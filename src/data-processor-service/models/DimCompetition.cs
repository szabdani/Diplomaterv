using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores the competition's source references, name and country.
/// </summary>
[Table("dim_competition", Schema = "dwh")]
public class DimCompetition
{
    [Key]
    [Column("competition_id")]
    public int CompetitionId { get; set; }

    [Column("wy_competition_id")]
    public int? WyCompetitionId { get; set; }

    [Column("tm_competition_id")]
    [MaxLength(8)]
    public string? TmCompetitionId { get; set; }

    [Column("cap_competition_slug")]
    public string? CapCompetitionSlug { get; set; }

    [Column("name")]
    [Required]
    public string Name { get; set; } = null!;

    [Column("country")]
    [Required]
    public string Country { get; set; } = null!;

    public ICollection<DimTeam> Teams { get; set; } = new List<DimTeam>();
    public ICollection<DimMatch> Matches { get; set; } = new List<DimMatch>();
}
