using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores a player's market value information: date, value, and club.
/// Foreign key to the player.
/// </summary>
[Table("fact_market_value", Schema = "dwh")]
public class FactMarketValue
{
    [Key]
    [Column("market_value_id")]
    public long MarketValueId { get; set; }

    [Column("player_id")]
    public int PlayerId { get; set; }

    [Column("market_value_date")]
    public DateOnly MarketValueDate { get; set; }

    [Column("market_value_eur")]
    public decimal MarketValueEur { get; set; }

    [Column("club_at_valuation")]
    public string? ClubAtValuation { get; set; }

    [ForeignKey(nameof(PlayerId))]
    public DimPlayer Player { get; set; }
}
