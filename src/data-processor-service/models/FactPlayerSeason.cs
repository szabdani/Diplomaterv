using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DataProcessor.Model;

/// <summary>
/// Stores a player's statistical KPIs for a season, in a competition:
/// - General information: player, team, competition, position, season label
/// - Playing-time context: matches played, minutes played, matches available
/// - Statistical KPIs: per-90 KPIs and aggregated pillar scores
/// - Aggregated pillar scores: for each of the 6 pillars
/// - Foreign key references: player, team, competition, position
/// </summary>
[Table("fact_player_season", Schema = "dwh")]
public class FactPlayerSeason
{
    [Key]
    [Column("player_season_id")]
    public long PlayerSeasonId { get; set; }

    [Column("player_id")]
    public int PlayerId { get; set; }

    [Column("team_id")]
    public int? TeamId { get; set; }

    [Column("competition_id")]
    public int? CompetitionId { get; set; }

    [Column("position_id")]
    public int? PositionId { get; set; }

    [Column("season_label")]
    [Required]
    public string SeasonLabel { get; set; } = "2017-2018";

    // =====================================================================
    // Playing-time context: matches played, minutes played, matches available
    // These are used as denominators for per-90 KPIs.
    // =====================================================================
    [Column("matches_played")]    public int? MatchesPlayed { get; set; }
    [Column("minutes_played")]    public int? MinutesPlayed { get; set; }
    [Column("matches_available")] public int? MatchesAvailable { get; set; }

    // =====================================================================
    // Statistical KPIs for each of the pillars
    // =====================================================================
    // Satt:
    [Column("spatial_xg_p90")]           public double? SpatialXgP90 { get; set; }
    [Column("finishing_eff_p90")]        public double? FinishingEffP90 { get; set; }
    [Column("goal_conversion_pct")]      public double? GoalConversionPct { get; set; }
    [Column("penalty_area_touches_p90")] public double? PenaltyAreaTouchesP90 { get; set; }

    // Splay:
    [Column("progressive_passes_p90")]      public double? ProgressivePassesP90 { get; set; }
    [Column("xt_p90")]                       public double? XtP90 { get; set; }
    [Column("final_third_box_entries_p90")] public double? FinalThirdBoxEntriesP90 { get; set; }
    [Column("key_passes_p90")]               public double? KeyPassesP90 { get; set; }
    [Column("xa_p90")]                       public double? XaP90 { get; set; }
    [Column("offensive_vaep_p90")]       public double? OffensiveVaepP90 { get; set; }

    // Sdef:
    [Column("high_press_recoveries_p90")] public double? HighPressRecoveriesP90 { get; set; }
    [Column("interceptions_p90")]           public double? InterceptionsP90 { get; set; }
    [Column("def_duels_won_p90")]          public double? DefDuelsWonP90 { get; set; }
    [Column("def_duel_win_pct")]           public double? DefDuelWinPct { get; set; }
    [Column("aerial_duels_won_p90")]       public double? AerialDuelsWonP90 { get; set; }
    [Column("aerial_duel_win_pct")]        public double? AerialDuelWinPct { get; set; }
    [Column("padj_def_actions_p90")]       public double? PadjDefActionsP90 { get; set; }
    [Column("defensive_vaep_p90")]         public double? DefensiveVaepP90 { get; set; }

    // Seff:
    [Column("pass_completion_pct")]  public double? PassCompletionPct { get; set; }
    [Column("overall_duel_win_pct")] public double? OverallDuelWinPct { get; set; }
    [Column("fouls_committed_p90")]  public double? FoulsCommittedP90 { get; set; }
    [Column("foul_to_card_pct")]   public double? FoulToCardPct { get; set; }
    [Column("availability_pct")]     public double? AvailabilityPct { get; set; }

    // Sgks:
    [Column("goals_prevented_p90")]  public double? GoalsPreventedP90 { get; set; }
    [Column("xg_weighted_save_pct")] public double? XgWeightedSavePct { get; set; }

    // Sgkd:
    [Column("sweeper_box_command_p90")]      public double? SweeperBoxCommandP90 { get; set; }
    [Column("progressive_distribution_p90")] public double? ProgressiveDistributionP90 { get; set; }

    // =====================================================================
    // Aggregated pillar scores
    // Normalized to [0,100] based on the percentile rank of the player 
    // among peers in the same position group.
    // The pillar scores are computed as a mean of the KPIs for that pillar.
    // =====================================================================
    [Column("score_att")]  public double? ScoreAtt { get; set; }
    [Column("score_play")] public double? ScorePlay { get; set; }
    [Column("score_def")]  public double? ScoreDef { get; set; }
    [Column("score_eff")]  public double? ScoreEff { get; set; }
    [Column("score_gks")]  public double? ScoreGks { get; set; }
    [Column("score_gkd")]  public double? ScoreGkd { get; set; }

    [Column("computed_at")]
    public DateTime ComputedAt { get; set; }

    // =====================================================================
    // Foreign key references: player, team, competition, position
    // =====================================================================
    [ForeignKey(nameof(PlayerId))]
    public DimPlayer? Player { get; set; }

    [ForeignKey(nameof(TeamId))]
    public DimTeam? Team { get; set; }

    [ForeignKey(nameof(CompetitionId))]
    public DimCompetition? Competition { get; set; }

    [ForeignKey(nameof(PositionId))]
    public DimPosition? Position { get; set; }
}
