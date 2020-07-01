// Wrapper for PRO2 compiler used to catch several
// exceptions and give an accurate verdict.

#include <iostream>
#include <unistd.h>
#include <signal.h>

using namespace std;

#undef main

int main__2 ();


int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(0);

    try {
        return main__2();
    } catch (bad_alloc& judge__e) {
        raise(SIGUSR1);
    } catch (exception& judge__e) {
        raise(SIGUSR2);
    } catch (...) {
        raise(SIGUSR2);
    }
}
