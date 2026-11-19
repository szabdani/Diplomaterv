using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores default tactical roles with names, codes and weights for the pillars.
/// </summary>
[Table("dim_role", Schema = "dwh")]
public class DimRole
{
    [Key]
    [Column("role_id")]
    public int RoleId { get; set; }

    [Column("role_name")]
    [Required]
    public string RoleName { get; set; } = null!;

    [Column("role_code")]
    public string? RoleCode { get; set; }

    [Column("w_att")]
    public double WAtt { get; set; }

    [Column("w_play")]
    public double WPlay { get; set; }

    [Column("w_def")]
    public double WDef { get; set; }

    [Column("w_eff")]
    public double WEff { get; set; }

    [Column("w_gks")]
    public double WGks { get; set; }

    [Column("w_gkd")]
    public double WGkd { get; set; }
}
