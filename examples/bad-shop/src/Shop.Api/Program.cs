var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContext<AppDbContext>(o => o.UseSqlServer(builder.Configuration.GetConnectionString("Default")));
builder.Services.AddHostedService<Worker>();
var app = builder.Build();
using (var scope = app.Services.CreateScope()) scope.ServiceProvider.GetRequiredService<AppDbContext>().Database.Migrate();
app.Run();
public class Worker : BackgroundService
{
    private readonly AppDbContext _db;
    public Worker(AppDbContext db) { _db = db; }
    protected override async Task ExecuteAsync(CancellationToken ct) { var x = await _db.Orders.CountAsync(ct); }
}
