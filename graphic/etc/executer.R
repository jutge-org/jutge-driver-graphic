
main_wrapper_R <- function() {
    source("program.R")
}


tryCatch(main_wrapper_R(),
    error = function(m) {
        library("tools")
        pskill(Sys.getpid(), signal=SIGKILL)
    }
)
