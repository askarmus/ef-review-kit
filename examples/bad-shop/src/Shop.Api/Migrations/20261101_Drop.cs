using Microsoft.EntityFrameworkCore.Migrations;
public partial class DropOld : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropColumn(name: "Legacy", table: "Orders");
        migrationBuilder.AlterColumn<string>(name: "Status", table: "Orders", maxLength: 20);
        migrationBuilder.RenameColumn(name: "Mail", table: "Orders", newName: "Email");
    }
    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropColumn(name: "X", table: "Orders");
    }
}
