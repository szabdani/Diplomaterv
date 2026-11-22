using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores a player's transfer information: date, from/to clubs, fee, and loan status.
/// Foreign key to the player.
/// </summary>
[Table("fact_transfer", Schema = "dwh")]
public class FactTransfer
{
    [Key]
    [Column("transfer_id")]
    public long TransferId { get; set; }

    [Column("player_id")]
    public int PlayerId { get; set; }

    [Column("transfer_date")]
    public DateOnly? TransferDate { get; set; }

    [Column("from_club")]
    public string? FromClub { get; set; }

    [Column("to_club")]
    public string? ToClub { get; set; }

    [Column("fee_eur")]
    public decimal? FeeEur { get; set; }

    [Column("is_loan")]
    public bool IsLoan { get; set; }

    [ForeignKey(nameof(PlayerId))]
    public DimPlayer? Player { get; set; }

}
