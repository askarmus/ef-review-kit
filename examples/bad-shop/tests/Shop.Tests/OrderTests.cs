public class OrderTests { void Setup() { var o = new DbContextOptionsBuilder<AppDbContext>().UseInMemoryDatabase("t").Options; } }
