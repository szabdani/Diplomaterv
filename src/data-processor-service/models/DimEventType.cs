using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores the event name for the Wyscout event ID
/// </summary>
[Table("dim_event_type", Schema = "dwh")]
public class DimEventType
{
    [Key]
    [Column("event_type_id")]
    public int EventTypeId { get; set; }

    [Column("wy_event_type_id")]
    public int WyEventTypeId { get; set; }

    [Column("event_name")]
    [Required]
    public string EventName { get; set; } = null!;
}
