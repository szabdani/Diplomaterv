using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores the sub-event name for the Wyscout sub-event ID
/// </summary>
[Table("dim_sub_event_type", Schema = "dwh")]
public class DimSubEventType
{
    [Key]
    [Column("sub_event_type_id")]
    public int SubEventTypeId { get; set; }

    [Column("wy_sub_event_type_id")]
    public int WySubEventTypeId { get; set; }

    [Column("sub_event_name")]
    [Required]
    public string SubEventName { get; set; } = null!;
}