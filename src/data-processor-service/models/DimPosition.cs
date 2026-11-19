using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores the position's short code and name from Wyscout and detailed name from Transfermarkt.
/// position_group is the peer bucket used for percentile standardisation of KPIs.
/// </summary>
[Table("dim_position", Schema = "dwh")]
public class DimPosition
{
    [Key]
    [Column("position_id")]
    public int PositionId { get; set; }

    /// <summary>
    /// Wyscout position code: 2-letter code for the position.
    /// 'GK','DF','MD','FW'
    /// </summary>
    [Column("wy_position_code")]
    [MaxLength(2)]
    public string? WyPositionCode { get; set; }               

    [Column("wy_position_name")]
    public string? WyPositionName { get; set; }

    [Column("tm_detailed_name")]
    public string? TmDetailedName { get; set; }

    /// <summary>
    /// How player KPIs are standardised for percentile ranking. Grouping is based on the position's role in the team.
    /// 'Goalkeeper'
    /// 'Full-Back', 'Center-Back'
    /// 'Defensive Midfielder', 'Central Midfielder', 'Attacking Midfielder'
    /// 'Wide Attacker', 'Center Forward'
    /// </summary>
    [Column("position_group")]
    public string? PositionGroup { get; set; }

    public ICollection<DimPlayer> Players { get; set; } = new List<DimPlayer>();
}
