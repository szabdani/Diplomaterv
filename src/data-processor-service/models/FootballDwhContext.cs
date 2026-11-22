using Microsoft.EntityFrameworkCore;

namespace DataProcessor.Model;

/// <summary>
/// EF Core context for the dwh-db PostgreSQL Data Warehouse.
/// Contains the analytical star schema:
/// Dimensions: dim_competition, dim_team, dim_player, dim_position, dim_match, dim_role, dim_event_type, dim_sub_event_type
/// Facts: fact_match_event, fact_player_season, fact_player_salary, fact_market_value, fact_transfer, fact_injury
/// Indexes and seed data are also defined here.
/// </summary>
public class FootballDwhContext : DbContext
{
    public FootballDwhContext(DbContextOptions<FootballDwhContext> options) : base(options) { }

    // Dimensions
    public DbSet<DimCompetition> Competitions => Set<DimCompetition>();
    public DbSet<DimTeam> Teams => Set<DimTeam>();
    public DbSet<DimPlayer> Players => Set<DimPlayer>();
    public DbSet<DimPosition> Positions => Set<DimPosition>();
    public DbSet<DimMatch> Matches => Set<DimMatch>();
    public DbSet<DimRole> Roles => Set<DimRole>();
    public DbSet<DimEventType> EventTypes => Set<DimEventType>();
    public DbSet<DimSubEventType> SubEventTypes => Set<DimSubEventType>();

    // Facts
    public DbSet<FactMatchEvent> MatchEvents => Set<FactMatchEvent>();
    public DbSet<FactPlayerSeason> PlayerSeasons => Set<FactPlayerSeason>();
    public DbSet<FactPlayerSalary> PlayerSalaries => Set<FactPlayerSalary>();
    public DbSet<FactMarketValue> MarketValues => Set<FactMarketValue>();
    public DbSet<FactTransfer> Transfers => Set<FactTransfer>();
    public DbSet<FactInjury> Injuries => Set<FactInjury>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.HasDefaultSchema("dwh");

        ConfigureConstraintsAndIndexes(b);
        ConfigureDecimalPrecision(b);
        SeedReferenceData(b);
    }

    // =====================================================================
    // Natural-key uniqueness + query indexes
    // =====================================================================
    private static void ConfigureConstraintsAndIndexes(ModelBuilder b)
    {
        b.Entity<DimCompetition>().HasIndex(x => x.WyCompetitionId).IsUnique();
        b.Entity<DimCompetition>().HasIndex(x => x.TmCompetitionId).IsUnique();
        b.Entity<DimCompetition>().HasIndex(x => x.CapCompetitionSlug).IsUnique();

        b.Entity<DimTeam>().HasIndex(x => x.WyTeamId).IsUnique();
        b.Entity<DimTeam>().HasIndex(x => x.TmClubId).IsUnique();
        b.Entity<DimTeam>().HasIndex(x => x.CapClubSlug).IsUnique();
        b.Entity<DimTeam>().HasIndex(x => x.CompetitionId);

        b.Entity<DimPlayer>().HasIndex(x => x.WyPlayerId).IsUnique();
        b.Entity<DimPlayer>().HasIndex(x => x.TmPlayerId).IsUnique();
        b.Entity<DimPlayer>().HasIndex(x => x.PositionId);
        b.Entity<DimPlayer>().HasIndex(x => x.CurrentTeamId);

        b.Entity<DimMatch>().HasIndex(x => x.WyMatchId).IsUnique();
        b.Entity<DimMatch>().HasIndex(x => x.CompetitionId);
        b.Entity<DimMatch>().HasIndex(x => x.MatchDate);

        b.entity<DimPosition>().HasIndex(x => x.WyPositionCode).IsUnique();
        b.entity<DimRole>().HasIndex(x => x.RoleName).IsUnique();
        b.Entity<DimEventType>().HasIndex(x => x.WyEventTypeId).IsUnique();
        b.Entity<DimSubEventType>().HasIndex(x => x.WySubEventTypeId).IsUnique();

        b.Entity<FactMatchEvent>().HasIndex(x => x.WyEventId).IsUnique();
        b.Entity<FactMatchEvent>().HasIndex(x => x.MatchId);
        b.Entity<FactMatchEvent>().HasIndex(x => x.PlayerId);
        b.Entity<FactMatchEvent>().HasIndex(x => new { x.EventTypeId, x.SubEventTypeId });

        b.Entity<FactPlayerSeason>().HasIndex(x => new { x.PlayerId, x.CompetitionId, x.SeasonLabel }).IsUnique();
        b.Entity<FactPlayerSeason>().HasIndex(x => x.PositionId);
        b.Entity<FactPlayerSeason>().HasIndex(x => x.CompetitionId);
        b.Entity<FactPlayerSeason>().Property(x => x.ComputedAt).HasDefaultValueSql("now()");

        b.Entity<FactMarketValue>().HasIndex(x => new { x.PlayerId, x.MarketValueDate }).IsUnique();
        b.Entity<FactMarketValue>().HasIndex(x => x.PlayerId);
        b.Entity<FactPlayerSalary>().HasIndex(x => new { x.PlayerId, x.SeasonLabel }).IsUnique();
        b.Entity<FactTransfer>().HasIndex(x => x.PlayerId);
        b.Entity<FactInjury>().HasIndex(x => x.PlayerId);

        // dim_match references dim_team twice (home/away)
        // Disable cascade to avoid multiple-cascade-path errors.
        b.Entity<DimMatch>()
            .HasOne(x => x.HomeTeam).WithMany()
            .HasForeignKey(x => x.HomeTeamId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<DimMatch>()
            .HasOne(x => x.AwayTeam).WithMany()
            .HasForeignKey(x => x.AwayTeamId).OnDelete(DeleteBehavior.Restrict);
    }

    // =====================================================================
    // Set precision for decimal columns
    // =====================================================================
    private static void ConfigureDecimalPrecision(ModelBuilder b)
    {
        b.Entity<DimRole>().Property(x => x.WAtt).HasPrecision(4, 3);
        b.Entity<DimRole>().Property(x => x.WPlay).HasPrecision(4, 3);
        b.Entity<DimRole>().Property(x => x.WDef).HasPrecision(4, 3);
        b.Entity<DimRole>().Property(x => x.WEff).HasPrecision(4, 3);
        b.Entity<DimRole>().Property(x => x.WGks).HasPrecision(4, 3);
        b.Entity<DimRole>().Property(x => x.WGkd).HasPrecision(4, 3);

        b.Entity<FactPlayerSalary>().Property(x => x.WeeklyWageEur).HasPrecision(14, 2);
        b.Entity<FactPlayerSalary>().Property(x => x.AnnualWageEur).HasPrecision(14, 2);
        b.Entity<FactMarketValue>().Property(x => x.MarketValueEur).HasPrecision(14, 2);
        b.Entity<FactTransfer>().Property(x => x.FeeEur).HasPrecision(14, 2);
    }

    // =====================================================================
    // Static reference data seeded into the warehouse
    // =====================================================================
    private static void SeedReferenceData(ModelBuilder b)
    {
        // Default tactical roles with their pillar weight vectors
        b.Entity<DimRole>().HasData(
            new DimRole { RoleId = 1, RoleName = "Shot-Stopper (GK)",         RoleCode = "GK", WAtt = 0.00m, WPlay = 0.00m, WDef = 0.00m, WEff = 0.15m, WGks = 0.70m, WGkd = 0.15m },
            new DimRole { RoleId = 2, RoleName = "Sweeper-Keeper (GK)",       RoleCode = "GK", WAtt = 0.00m, WPlay = 0.05m, WDef = 0.00m, WEff = 0.15m, WGks = 0.35m, WGkd = 0.45m },
            new DimRole { RoleId = 3, RoleName = "Centre-Back (CB)",          RoleCode = "CB", WAtt = 0.05m, WPlay = 0.15m, WDef = 0.45m, WEff = 0.35m, WGks = 0.00m, WGkd = 0.00m },
            new DimRole { RoleId = 4, RoleName = "Full-Back (LB/RB)",         RoleCode = "FB", WAtt = 0.10m, WPlay = 0.30m, WDef = 0.35m, WEff = 0.25m, WGks = 0.00m, WGkd = 0.00m },
            new DimRole { RoleId = 5, RoleName = "Defensive Midfielder (DM)", RoleCode = "DM", WAtt = 0.05m, WPlay = 0.30m, WDef = 0.40m, WEff = 0.25m, WGks = 0.00m, WGkd = 0.00m },
            new DimRole { RoleId = 6, RoleName = "Central Midfielder (CM)",   RoleCode = "CM", WAtt = 0.15m, WPlay = 0.40m, WDef = 0.25m, WEff = 0.20m, WGks = 0.00m, WGkd = 0.00m },
            new DimRole { RoleId = 7, RoleName = "Attacking Midfielder (AM)", RoleCode = "AM", WAtt = 0.30m, WPlay = 0.45m, WDef = 0.10m, WEff = 0.15m, WGks = 0.00m, WGkd = 0.00m },
            new DimRole { RoleId = 8, RoleName = "Winger (RW/LW)",            RoleCode = "W",  WAtt = 0.35m, WPlay = 0.40m, WDef = 0.10m, WEff = 0.15m, WGks = 0.00m, WGkd = 0.00m },
            new DimRole { RoleId = 9, RoleName = "Striker (ST)",              RoleCode = "ST", WAtt = 0.55m, WPlay = 0.25m, WDef = 0.05m, WEff = 0.15m, WGks = 0.00m, WGkd = 0.00m }
        );

        // Wyscout top-level event types (eventId -> eventName)
        b.Entity<DimEventType>().HasData(
            new DimEventType { EventTypeId = 1,  WyEventTypeId = 1,  EventName = "Duel" },
            new DimEventType { EventTypeId = 2,  WyEventTypeId = 2,  EventName = "Foul" },
            new DimEventType { EventTypeId = 3,  WyEventTypeId = 3,  EventName = "Free Kick" },
            new DimEventType { EventTypeId = 4,  WyEventTypeId = 4,  EventName = "Goalkeeper leaving line" },
            new DimEventType { EventTypeId = 5,  WyEventTypeId = 5,  EventName = "Interruption" },
            new DimEventType { EventTypeId = 6,  WyEventTypeId = 6,  EventName = "Offside" },
            new DimEventType { EventTypeId = 7,  WyEventTypeId = 7,  EventName = "Others on the ball" },
            new DimEventType { EventTypeId = 8,  WyEventTypeId = 8,  EventName = "Pass" },
            new DimEventType { EventTypeId = 9,  WyEventTypeId = 9,  EventName = "Save attempt" },
            new DimEventType { EventTypeId = 10, WyEventTypeId = 10, EventName = "Shot" }
        );

        // Wyscout sub-event types (subEventId -> subEventName)
        b.Entity<DimSubEventType>().HasData(
            // Duel (1)
            new DimSubEventType { SubEventTypeId = 1,  WySubEventTypeId = 10, SubEventName = "Air duel" },
            new DimSubEventType { SubEventTypeId = 2,  WySubEventTypeId = 11, SubEventName = "Ground attacking duel" },
            new DimSubEventType { SubEventTypeId = 3,  WySubEventTypeId = 12, SubEventName = "Ground defending duel" },
            new DimSubEventType { SubEventTypeId = 4,  WySubEventTypeId = 13, SubEventName = "Ground loose ball duel" },

            // Foul (2)
            new DimSubEventType { SubEventTypeId = 5,  WySubEventTypeId = 20, SubEventName = "Foul" },
            new DimSubEventType { SubEventTypeId = 6,  WySubEventTypeId = 21, SubEventName = "Hand foul" },
            new DimSubEventType { SubEventTypeId = 7,  WySubEventTypeId = 22, SubEventName = "Late card foul" },
            new DimSubEventType { SubEventTypeId = 8,  WySubEventTypeId = 23, SubEventName = "Out of game foul" },
            new DimSubEventType { SubEventTypeId = 9,  WySubEventTypeId = 24, SubEventName = "Protest" },
            new DimSubEventType { SubEventTypeId = 10, WySubEventTypeId = 25, SubEventName = "Simulation" },
            new DimSubEventType { SubEventTypeId = 11, WySubEventTypeId = 26, SubEventName = "Time lost foul" },
            new DimSubEventType { SubEventTypeId = 12, WySubEventTypeId = 27, SubEventName = "Violent Foul" },

            // Free Kick (3)
            new DimSubEventType { SubEventTypeId = 13, WySubEventTypeId = 30, SubEventName = "Corner" },
            new DimSubEventType { SubEventTypeId = 14, WySubEventTypeId = 31, SubEventName = "Free Kick" },
            new DimSubEventType { SubEventTypeId = 15, WySubEventTypeId = 32, SubEventName = "Free kick cross" },
            new DimSubEventType { SubEventTypeId = 16, WySubEventTypeId = 33, SubEventName = "Free kick shot" },
            new DimSubEventType { SubEventTypeId = 17, WySubEventTypeId = 34, SubEventName = "Goal kick" },
            new DimSubEventType { SubEventTypeId = 18, WySubEventTypeId = 35, SubEventName = "Penalty" },
            new DimSubEventType { SubEventTypeId = 19, WySubEventTypeId = 36, SubEventName = "Throw in" },

            // Goalkeeper leaving line (4)
            new DimSubEventType { SubEventTypeId = 20, WySubEventTypeId = 40, SubEventName = "Goalkeeper leaving line" },

            // Interruption (5)
            new DimSubEventType { SubEventTypeId = 21, WySubEventTypeId = 50, SubEventName = "Ball out of the field" },
            new DimSubEventType { SubEventTypeId = 22, WySubEventTypeId = 51, SubEventName = "Whistle" },

            // Others on the ball (7)
            new DimSubEventType { SubEventTypeId = 23, WySubEventTypeId = 70, SubEventName = "Acceleration" },
            new DimSubEventType { SubEventTypeId = 24, WySubEventTypeId = 71, SubEventName = "Clearance" },
            new DimSubEventType { SubEventTypeId = 25, WySubEventTypeId = 72, SubEventName = "Touch" },

            // Pass (8)
            new DimSubEventType { SubEventTypeId = 26, WySubEventTypeId = 80, SubEventName = "Cross" },
            new DimSubEventType { SubEventTypeId = 27, WySubEventTypeId = 81, SubEventName = "Hand pass" },
            new DimSubEventType { SubEventTypeId = 28, WySubEventTypeId = 82, SubEventName = "Head pass" },
            new DimSubEventType { SubEventTypeId = 29, WySubEventTypeId = 83, SubEventName = "High pass" },
            new DimSubEventType { SubEventTypeId = 30, WySubEventTypeId = 84, SubEventName = "Launch" },
            new DimSubEventType { SubEventTypeId = 31, WySubEventTypeId = 85, SubEventName = "Simple pass" },
            new DimSubEventType { SubEventTypeId = 32, WySubEventTypeId = 86, SubEventName = "Smart pass" },

            // Save attempt (9)
            new DimSubEventType { SubEventTypeId = 33, WySubEventTypeId = 90, SubEventName = "Reflexes" },
            new DimSubEventType { SubEventTypeId = 34, WySubEventTypeId = 91, SubEventName = "Save attempt" },
            
            // Shot (10)
            new DimSubEventType { SubEventTypeId = 35, WySubEventTypeId = 100, SubEventName = "Shot" }
        );
    }
}