fn main() -> std::io::Result<()> {
    codinal_runtime::parent_watchdog::start_from_environment()?;
    codinal_runtime::run_from_environment()
}
