/*
 GHDL VHPI interface for MyHDL
 
 Author:  Oscar Diaz <oscar.dc0@gmail.com>
 Date:    16-02-2013

 This code is free software; you can redistribute it and/or
 modify it under the terms of the GNU Lesser General Public
 License as published by the Free Software Foundation; either
 version 3 of the License, or (at your option) any later version.

 This code is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 Lesser General Public License for more details.

 You should have received a copy of the GNU Lesser General Public
 License along with this package; if not, see 
 <http://www.gnu.org/licenses/>.
 
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <linux/un.h>
#include <netinet/ip.h>
#include <netdb.h>

// #define VHPI_DEBUG 1
// #define VHPI_GDBWAIT 1

#ifdef VHPI_DEBUG
#define d_perror(x) perror(x)
#define debug(...)  printf(__VA_ARGS__)
#else
#define d_perror(x)
#define debug(...)
#endif

// bit masks for sigentry.flags
#define FLAG_HAS_CHANGED  0x1
#define FLAG_INITIAL_VAL  0x2
#define FLAG_UNCONFIGURED 0x4

// codes for update_signal return value
#define UPDATE_ERROR -1 
#define UPDATE_END    0 // end simulation
#define UPDATE_SIGNAL 1 // next update need a signal trigger or small time delay
#define UPDATE_TIME   2 // next update will be at a time delay
#define UPDATE_DELTA  3 // next update need a delta step

#define MAX_STRING 256

// static info
static int init_connection_flag = 0;
static int conn_sockfd = -1;
static int rpipe = 0;
static int wpipe = 0;

static char cosim_from_signals[MAX_STRING];
static char cosim_to_signals[MAX_STRING];
static int cosim_init_flag = 0;

static uint64_t vhdl_time_res = 0;
static uint64_t vhdl_curtime = 0;
static uint64_t myhdl_curtime = 0;
static uint64_t myhdl_next_trigger = 0;

// string objects from GHDL
struct array_bounds {
    int left;
    int right;
    char dir; // 0x0: to, 0x1: downto
    unsigned int len;
};

/*
Arrays: pointer "base" holds data in memory
pos 0 on memory holds left index, pos <len-1> holds right index
dir = 0: bitwise little-endian, dir = 1: bitwise big-endian
*/

typedef struct ghdl_string_s {
    char *base;
    struct array_bounds *bounds;
} ghdl_string;

typedef struct ghdl_std_logic_vector_s {
    uint8_t *base;
    struct array_bounds *bounds;
} ghdl_std_logic_vector;

/*
    std_logic type:
    0: 'U',  -- Uninitialized
    1: 'X',  -- Forcing  Unknown
    2: '0',  -- Forcing  0
    3: '1',  -- Forcing  1
    4: 'Z',  -- High Impedance
    5: 'W',  -- Weak     Unknown
    6: 'L',  -- Weak     0
    7: 'H',  -- Weak     1
    8: '-'   -- Don't care
*/
static const char std_logic_charmap[] = {'U', 'X', '0', '1', 'Z', 'W', 'L', 'H', '-'};
#define STD_LOGIC_VAL0 0x2
#define STD_LOGIC_VAL1 0x3

// signal mapping
static int cosim_fs_count = 0;
static int cosim_ts_count = 0;
static int cosim_fs_bitsize = 0;
static int cosim_ts_bitsize = 0;

typedef struct sigentry {
    char name[MAX_STRING];
    int size_reported; 
    int flags;
    struct array_bounds bounds;
    ghdl_std_logic_vector * ptrvector;
} sigentry_t;

static sigentry_t * cosim_from_set;
static sigentry_t * cosim_to_set;
uint8_t * cosim_to_sigcopy;

// prototypes
static int init_connection();
static int init_unix_socket(char * socket_path);
static int init_inet_socket(char * socket_path);
static void d_print_rawdata(ghdl_std_logic_vector * data, char * premsg);
static void d_print_sigset(sigentry_t * base, int len, char * premsg);
static int parse_init(char * input);
static void sigset_config(sigentry_t * base, int count, ghdl_std_logic_vector * vector);
static void sigset_to_update(ghdl_std_logic_vector * to_vector);
static int sendrecv(char * buf, int max_len);
static int std_logic_vector_to_string(ghdl_std_logic_vector * data, struct array_bounds * opt_bounds, char * binbuf, char * hexbuf, int max_len);
static int hex_to_int(char ch);
static char int_to_hex(int num);

int startup_simulation (uint64_t time, uint64_t time_res, ghdl_string * from_signals, ghdl_string * to_signals);
int update_signal (ghdl_std_logic_vector * datain, ghdl_std_logic_vector * dataout, uint64_t time);
uint64_t next_timetrigger(uint64_t curtime);

static int init_connection()
{
    char *s;
    char *w;
    char *r;
    int sockfd;

    if (init_connection_flag) {
        return 0;
    }
    
    s = getenv("MYHDL_SOCKET");
    w = getenv("MYHDL_TO_PIPE");
    r = getenv("MYHDL_FROM_PIPE");
    
    if (s != NULL) {
        // sockets available, use as first choice
        
        /* format for socket path:
         <hostname>:<port> for IP sockets
         <filepath> for unix sockets (assume full path)
         */ 
        if(strchr(s, ':') != NULL) {
            // format candidate for inet socket
            sockfd = init_inet_socket(s);
        } else {
            // assume UNIX sockets
            sockfd = init_unix_socket(s);
        }
        // if any error ocurred before, was already reported
        if(sockfd < 0) return -1;
        conn_sockfd = sockfd;
        
    } else if ((w != NULL) && (r != NULL)) {
        // fallback to unix pipes
        wpipe = atoi(w);
        rpipe = atoi(r);
        debug("DEBUG: setup pipes done.\n");
    } else {
        debug("VHPI: unable to set a connection with MyHDL.\n");
        return -1;
    }
    
    init_connection_flag = 1;
    return 0;
}

static int init_unix_socket(char * socket_path)
{
    int sockfd;
    struct sockaddr_un unix_addr;
    
    sockfd = socket(PF_UNIX, SOCK_STREAM, 0);
    if(sockfd < 0) {
        d_perror("socket");
        debug("VHPI: error on UNIX socket\n");
        return -1;
    } 
    
    unlink(socket_path);
    unix_addr.sun_family = AF_UNIX;
    snprintf(unix_addr.sun_path, UNIX_PATH_MAX, socket_path);
    
    if (connect(sockfd, (struct sockaddr *) &unix_addr, sizeof(unix_addr)) == -1) {
        d_perror("connect");
        debug("VHPI: UNIX socket, error on connect\n");
        close(sockfd);
        return -1;
    }
    debug("DEBUG: setup UNIX socket done (%s).\n", socket_path);
    return sockfd;
}

static int init_inet_socket(char * socket_path)
{
    int retval, sockfd, hostlen;
    char hostname[MAX_STRING], portname[MAX_STRING];
    char *bufptr;
    struct addrinfo * result;
    
    bufptr = strrchr(socket_path, ':');
    hostlen = (int) (bufptr - socket_path);
    strncpy(hostname, socket_path, hostlen);
    bufptr++;
    strncpy(portname, bufptr, hostlen);
    
    retval = getaddrinfo(hostname, portname, NULL, &result);
    
    if(retval < 0) {
        debug("VHPI: error on INET getaddrinfo (reason: %s).\n", gai_strerror(retval));
        return -1;
    } 
    
    if(result->ai_family == AF_INET) {
        sockfd = socket(PF_INET, SOCK_STREAM, 0);
    } else if(result->ai_family == AF_INET6) {
        sockfd = socket(PF_INET6, SOCK_STREAM, 0);
    } 
    
    if(sockfd < 0) {
        d_perror("socket");
        debug("VHPI: error on INET socket creation.\n");
        freeaddrinfo(result);
        return -1;
    } 
    
    if (connect(sockfd, result->ai_addr, result->ai_addrlen) == -1) {
        d_perror("connect");
        debug("VHPI: error on INET connect.\n");
        close(sockfd);
        freeaddrinfo(result);
        return -1;
    }
    debug("VHPI: INET socket (%s) done. sockfd=%d .\n", socket_path, sockfd);
    
    freeaddrinfo(result);    
    return sockfd;
}

#ifdef VHPI_DEBUG
static void d_print_rawdata(ghdl_std_logic_vector * data, char * premsg)
{
    int i;
    char buf[MAX_STRING];
    char * dirstr;
    
    if(data->bounds->dir) {
        dirstr = "downto";
    } else {
        dirstr = "to";
    }
    for(i = 0; i < data->bounds->len; i++) {
        buf[i] = std_logic_charmap[data->base[i]];
    }
    buf[i] = '\0';
    debug("VHPI: %s binary data (%d %s %d): %s\n", premsg, data->bounds->left, dirstr, data->bounds->right, buf);
}

static void d_print_sigset(sigentry_t * base, int len, char * premsg)
{
    int i;
    char binbuf[MAX_STRING];
    char intbuf[MAX_STRING];
    char *dirstr;
    
    debug("VHPI: %s sigentry output\n", premsg);
    for(i = 0; i < len; i++) {
        if(base[i].bounds.dir) {
            dirstr = "downto";
        } else {
            dirstr = "to";
        }
        debug(" %s (%d %s %d)<%d bits, flags 0x%x>", base[i].name, base[i].bounds.left, dirstr, base[i].bounds.right, base[i].bounds.len, base[i].flags);
        if(std_logic_vector_to_string(base[i].ptrvector, &(base[i].bounds), binbuf, intbuf, MAX_STRING) == 0) {
            debug(" {%s} [%s]\n", binbuf, intbuf);
        } else {
            debug(" * Error in string conversion *\n");
        }
    }
}
#else
static void d_print_rawdata(ghdl_std_logic_vector * data, char * premsg)
{
    return;
}

static void d_print_sigset(sigentry_t * base, int len, char * premsg)
{
    return;
}
#endif


static int parse_init(char * input)
{
    char buf[MAX_STRING];
    char *bufptr, *token;
    int names_count, sizes_count;
    long tmpnumber;
    
    strncpy(buf, input, MAX_STRING);
    
    // input format: <name> <size> ... <name-n> <size-n>
    
    token = strtok_r(buf, " ", &bufptr);
    for(names_count = sizes_count = 0; token != NULL;) {
        // first element: name
        names_count++;
        // ---
        token = strtok_r(NULL, " ", &bufptr);
        if(token == NULL) {
            break;
        }
        // second element: bitsize
        // check if is a positive number (non-zero)
        if(sscanf(token, "%ld", &tmpnumber) < 0) {
            break;
        }
        if(tmpnumber <= 0) {
            break;
        }
        sizes_count++;
        // ---
        token = strtok_r(NULL, " ", &bufptr);
    }
    if(names_count != sizes_count) {
        return -1;
    } else {
        return names_count;
    }
}

static void sigset_config(sigentry_t * base, int count, ghdl_std_logic_vector * vector)
{
    int i, curbit;
    
    // NOTE: always start with LSB bit when assigning signals in correct order
    curbit = 0;
    for(i = 0; i < count; i++) {
        if (vector->bounds->dir) {
            base[i].bounds.left = curbit + (base[i].size_reported - 1);
            base[i].bounds.right = curbit;
        } else {
            base[i].bounds.left = curbit;
            base[i].bounds.right = curbit + (base[i].size_reported - 1);
        }
        base[i].bounds.dir = vector->bounds->dir;
        base[i].bounds.len = base[i].size_reported;
        base[i].ptrvector = vector;
        base[i].flags &= ~FLAG_UNCONFIGURED;
        if (vector->bounds->dir) {
            debug("VHPI: config sigentry name=%s (%d downto %d) <%d bits> ptrvector at %p\n", base[i].name, base[i].bounds.left, base[i].bounds.right, base[i].bounds.len, base[i].ptrvector);
        } else {
            debug("VHPI: config sigentry name=%s (%d to %d) <%d bits> ptrvector at %p\n", base[i].name, base[i].bounds.left, base[i].bounds.right, base[i].bounds.len, base[i].ptrvector);
        }
        curbit += base[i].size_reported;
    }
}

static void sigset_to_update(ghdl_std_logic_vector * to_vector)
{
    int i, j, curbit, bitidx;
    
    curbit = 0;
    for(i = 0; i < cosim_ts_count; i++) {
        for(j = 0; (curbit < cosim_ts_bitsize) && (j < cosim_to_set[i].bounds.len); curbit++, j++) {
            if (to_vector->bounds->dir) {
                // downto: invert bit index
                bitidx = (to_vector->bounds->len - 1) - curbit;
            } else {
                bitidx = curbit;
            }
            if(to_vector->base[bitidx] != cosim_to_sigcopy[bitidx]) {
                debug("VHPI: update TO_set name=%s : curbit %d bitidx %d : %c -> %c\n", cosim_to_set[i].name, curbit, bitidx, std_logic_charmap[cosim_to_sigcopy[bitidx]], std_logic_charmap[to_vector->base[bitidx]]);
                cosim_to_set[i].flags |= FLAG_HAS_CHANGED;
                cosim_to_sigcopy[bitidx] = to_vector->base[bitidx];
            }
        }
    }
}

static int sendrecv(char * buf, int max_len)
{
    int retval, nbytes;
    
    nbytes = strlen(buf);
    
    debug("VHPI: wpipe sending  >>>%s<<<\n", buf);
    
    if(conn_sockfd > 0) {
        retval = send(conn_sockfd, buf, nbytes, MSG_NOSIGNAL);
    } else {
        retval = write(wpipe, buf, nbytes);
    }
    
    if(retval <= 0) {
        // EPIPE error: simply return 0 bytes read
        if(errno == EPIPE) {
            return 0;
        }
        d_perror("send");
        debug("VHPI: error on send (%d)\n", retval);
        return retval;
    }
    
    if(conn_sockfd > 0) {
        nbytes = recv(conn_sockfd, buf, max_len, MSG_NOSIGNAL);
    } else {
        nbytes = read(rpipe, buf, max_len);
    }
    
    if(nbytes < 0) {
        d_perror("recv");
        debug("VHPI: error on recv (%d)\n", nbytes);
        return nbytes;
    }
    if(nbytes == 0) return nbytes;

    if(nbytes < max_len) {
        if(buf[nbytes] != '\0') {
            buf[nbytes] = '\0';
            nbytes++;
        }
        debug("VHPI: rpipe received >>>%s<<<\n", buf);
        return nbytes;
    } else {
        buf[max_len-1] = '\0';
        debug("VHPI: rpipe recv max >>>%s<<<\n", buf);
        return max_len;
    }
}

static int std_logic_vector_to_string(ghdl_std_logic_vector * data, struct array_bounds * opt_bounds, char * binbuf, char * hexbuf, int max_len)
{
    int j, k, l, hexval;
    uint8_t * bindata = data->base;
    struct array_bounds * bounds;
    
    if(opt_bounds == NULL) {
        bounds = data->bounds;
    } else {
        bounds = opt_bounds;
    }
    
    if(bounds->dir) {
        // "downto" order
        if(binbuf != NULL) {
            for(j = bounds->left, k = 0; (j >= bounds->right) && (k < max_len); j--, k++) {
                binbuf[k] = std_logic_charmap[bindata[(data->bounds->len -1) - j]];
            }
            binbuf[k] = '\0';
        }
        
        if(hexbuf != NULL) {
            if ((bounds->len % 4) == 0) {
                l = (bounds->len / 4) - 1;
            } else {
                l = bounds->len / 4;
            }
            
            if(l+1 > max_len) {
                return -1;
            }
            
            hexbuf[l+1] = '\0';
                
            for(hexval = 0, j = 0, k = bounds->right; k <= bounds->left ; k++) {
                if(bindata[(data->bounds->len - 1) - k] == STD_LOGIC_VAL1) {
                    hexval |= (1 << j);
                }
                if(j == 3) {
                    hexbuf[l] = int_to_hex(hexval);
                    j = 0;
                    hexval = 0;
                    l--;
                } else {
                    j++;
                }
            }
            if(j != 0) {
                hexbuf[l] = int_to_hex(hexval);
            }
        }
    } else {
        // "to" order
        if(binbuf != NULL) {
            for(j = bounds->left, k = 0; (j <= bounds->right) && (k < MAX_STRING); j++, k++) {
                binbuf[k] = std_logic_charmap[bindata[j]];
            }
            binbuf[k] = '\0';
        }
        
        if(hexbuf != NULL) {
            for(hexval = 0, j = 0, k = bounds->left, l = 0; k <= bounds->right ; k++) {
                if(bindata[k] == STD_LOGIC_VAL1) {
                    hexval |= (1 << j);
                }
                if(j == 3) {
                    hexbuf[l] = int_to_hex(hexval);
                    j = 0;
                    hexval = 0;
                    l++;
                    
                    if(l > max_len) {
                        return -1;
                    }
                } else {
                    j++;
                }
            }
            if(j == 0) {
                hexbuf[l] = '\0';
            } else {
                hexbuf[l] = int_to_hex(hexval);
                hexbuf[l+1] = '\0';
            }
        }
    }
    
    return 0;
}

static int hex_to_int(char ch)
{
    if((ch >= '0') && (ch <= '9')) { 
        return (ch - '0');
    }
    if((ch >= 'A') && (ch <= 'F')) {
        return (ch - 'A' + 0xa);
    }
    if((ch >= 'a') && (ch <= 'f')) {
        return (ch - 'a' + 0xa);
    }
    return -1;
}

static char int_to_hex(int num)
{
    if((num >= 0) && (num <= 9)) {
        return ('0' + ((char) num));
    }
    if((num >= 10) && (num <= 15)) {
        return ('a' + ((char) (num - 10)));
    }
    return ' ';
}

// ***** external interface to myhdl_vhpi_core *****

/** startup_simulation
 * called on the start of simulation
 * @param time current simulation time. Must be zero
 * @param time_res minimum time step in VHDL that correspond with one MyHDL time step
 * @param from_signals signal descriptions for MyHDL driven signals
 * @param to_signals signal descriptions for MyHDL read signals
 */
int startup_simulation (uint64_t time, uint64_t time_res, ghdl_string * from_signals, ghdl_string * to_signals)
{
    int retval, i, nbytes;
    char buf[MAX_STRING];
    char *bufptr, *token;
    
    debug("\nVHPI: startup_simulation:\n time = %llu\n time_res = %llu\n from_signals = <%s>\n to_signals = <%s>\n", (unsigned long long) time, (unsigned long long) time_res, from_signals->base, to_signals->base);
    
    // call once only
    if (cosim_init_flag) {
        debug("VHPI: startup_simulation called again.\n");
        return -1;
    }
    cosim_init_flag = 1;
    
    vhdl_time_res = time_res;
    vhdl_curtime = time;
    myhdl_curtime = time / vhdl_time_res;
    myhdl_next_trigger = 0;
    
    debug("VHPI: PID = %d.\n", getpid());
#ifdef VHPI_GDBWAIT
    debug("VHPI: Waiting 10 seconds to gdb attach.\n");
    sleep(10);
    debug("VHPI: ... Done. You should be gdb attached now.\n");
#endif
    
    retval = init_connection();
    if(retval < 0) {
        return retval;
    }
    
    strncpy(cosim_from_signals, from_signals->base, from_signals->bounds->len);
    strncpy(cosim_to_signals, to_signals->base, to_signals->bounds->len);
    
    // parse info
    cosim_fs_count = parse_init(cosim_from_signals);
    if(cosim_fs_count < 0) {
        debug("VHPI: parse error in from_signals (%s).\n", cosim_from_signals);
        return -1;
    }
    cosim_ts_count = parse_init(cosim_to_signals);
    if(cosim_ts_count < 0) {
        debug("VHPI: parse error in to_signals (%s).\n", cosim_to_signals);
        return -1;
    }
    
    cosim_from_set = (sigentry_t *) malloc(cosim_fs_count * sizeof(sigentry_t));
    cosim_to_set = (sigentry_t *) malloc(cosim_ts_count * sizeof(sigentry_t));
    if((cosim_from_set == NULL) || (cosim_to_set == NULL)) {
        d_perror("malloc");
        debug("VHPI: malloc error.\n");
        return -1;
    }
    
    // extract FROM data
    strncpy(buf, cosim_from_signals, MAX_STRING);
    token = strtok_r(buf, " ", &bufptr);
    for(i = 0; i < cosim_fs_count; i++) {
        // first element: name
        strncpy(cosim_from_set[i].name, token, MAX_STRING);
        token = strtok_r(NULL, " ", &bufptr);
        // second element: reported bitsize
        sscanf(token, "%i", &(cosim_from_set[i].size_reported));
        token = strtok_r(NULL, " ", &bufptr);
        // additional: flags and pointers initialization
        cosim_from_set[i].flags = FLAG_UNCONFIGURED;
        cosim_from_set[i].bounds.left = 0;
        cosim_from_set[i].bounds.right = 0;
        cosim_from_set[i].bounds.dir = 0;
        cosim_from_set[i].bounds.len = 0;
        cosim_from_set[i].ptrvector = NULL;
        // bitsize increment
        cosim_fs_bitsize += cosim_from_set[i].size_reported;
    }

    // extract TO data
    strncpy(buf, cosim_to_signals, MAX_STRING);
    token = strtok_r(buf, " ", &bufptr);
    for(i = 0; i < cosim_ts_count; i++) {
        // first element: name
        strncpy(cosim_to_set[i].name, token, MAX_STRING);
        token = strtok_r(NULL, " ", &bufptr);
        // second element: bitsize
        sscanf(token, "%i", &(cosim_to_set[i].size_reported));
        token = strtok_r(NULL, " ", &bufptr);
        // additional: value initialization
        cosim_to_set[i].flags = FLAG_INITIAL_VAL | FLAG_UNCONFIGURED;
        cosim_to_set[i].bounds.left = 0;
        cosim_to_set[i].bounds.right = 0;
        cosim_to_set[i].bounds.dir = 0;
        cosim_to_set[i].bounds.len = 0;
        cosim_to_set[i].ptrvector = NULL;
        // bitsize increment
        cosim_ts_bitsize += cosim_to_set[i].size_reported;
    }
    
    // TO signal copy, for keeping track of changes
    cosim_to_sigcopy = (uint8_t *) malloc(cosim_ts_bitsize * sizeof(uint8_t));
    if(cosim_to_sigcopy == NULL) {
        d_perror("malloc");
        debug("VHPI: malloc error.\n");
        return -1;
    }
    // 'U' value default
    memset(cosim_to_sigcopy, 0, cosim_ts_bitsize);
    
    debug("VHPI: FROM %d signals => %d bits\n", cosim_fs_count, cosim_fs_bitsize);
    debug("VHPI: TO %d signals => %d bits\n", cosim_ts_count, cosim_ts_bitsize);
    
    snprintf(buf, MAX_STRING, "FROM %lu %s ", (unsigned long) time, cosim_from_signals);
    
    nbytes = sendrecv(buf, MAX_STRING);
    if(nbytes <= 0) return retval;
    
    // check for OK
    if((buf[0] != 'O') && (buf[0] != 'K')) {
        debug("VHPI: error, MyHDL returned (%s).\n", buf);
        return -1;
    }
    
    snprintf(buf, MAX_STRING, "TO %lu %s ", (unsigned long) time, cosim_to_signals);
    
    nbytes = sendrecv(buf, MAX_STRING);
    if(nbytes <= 0) {
        return retval;
    }
    
    if((buf[0] != 'O') && (buf[0] != 'K')) {
        debug("VHPI: error, MyHDL returned (%s).\n", buf);
        return -1;
    }
    
    snprintf(buf, MAX_STRING, "START ");
    
    nbytes = sendrecv(buf, MAX_STRING);
    if(nbytes <= 0) {
        return retval;
    }
    
    if((buf[0] != 'O') && (buf[0] != 'K')) {
        debug("VHPI: error, MyHDL returned (%s).\n", buf);
        return -1;
    }
    
    debug("VHPI: startup_simulation: return 0\n");
    
    return 0;
}

/** update_signal
 * called on a VHDL event (on datain or after delay)
 * @param datain : input vector for TO signals
 * @param dataout : output vector for FROM signals
 * @param time : current VHDL time
 * 
 */
int update_signal (ghdl_std_logic_vector * datain, ghdl_std_logic_vector * dataout, uint64_t time)
{
    int retval, nbytes, i, j, k, l;
    char buf[MAX_STRING];
    char val[MAX_STRING];
    char * bufptr, *token;
    
    uint64_t myhdl_temptime;
    
    debug("VHPI: update_signal:\n datain = %p\n dataout = %p\n time = %llu\n", datain, dataout, (unsigned long long) time);
    
    retval = init_connection();
    if(retval < 0) {
        return UPDATE_ERROR;
    }
    
    d_print_rawdata(datain, "datain");
    
    // check configured state
    if(cosim_to_set[0].flags & FLAG_UNCONFIGURED) {
        sigset_config(cosim_to_set, cosim_ts_count, datain);
    } else {
        // check dir and len
        if (cosim_to_set[0].bounds.dir != datain->bounds->dir) {
            debug("VHPI: Inconsistent argument datain->bounds->dir(%d), should be (%d).\n", datain->bounds->dir, cosim_to_set[0].bounds.dir);
            return UPDATE_ERROR;
        }
        if(cosim_ts_bitsize != datain->bounds->len) {
            debug("VHPI: Inconsistent bitsize in datain->bounds->len(%d), should be (%d).\n", datain->bounds->len, cosim_ts_bitsize);
            return UPDATE_ERROR;
        }
    }
    if(cosim_from_set[0].flags & FLAG_UNCONFIGURED) {
        sigset_config(cosim_from_set, cosim_fs_count, dataout);
    } else {
        if (cosim_from_set[0].bounds.dir != dataout->bounds->dir) {
            debug("VHPI: Inconsistent argument dataout->bounds->dir(%d), should be (%d).\n", dataout->bounds->dir, cosim_from_set[0].bounds.dir);
            return UPDATE_ERROR;
        }
        if(cosim_fs_bitsize != dataout->bounds->len) {
            debug("VHPI: Inconsistent bitsize in dataout->bounds->len(%d), should be (%d).\n", dataout->bounds->len, cosim_fs_bitsize);
            return UPDATE_ERROR;
        }
    }
    
    // update vector on signal set TO
    for(i = 0; i < cosim_ts_count; i++) {
        cosim_to_set[i].ptrvector = datain;
    }
    
    d_print_sigset(cosim_to_set, cosim_ts_count, "TO_set");
    
    // prepare time counter
    vhdl_curtime = time;
    myhdl_temptime = time / vhdl_time_res;
    nbytes = snprintf(buf, MAX_STRING, "%llu ", (unsigned long long) myhdl_temptime);
    debug("VHPI: prev_myhdl_time = %llu , myhdl_time = %llu\n", (unsigned long long) myhdl_curtime, (unsigned long long) myhdl_temptime);
    myhdl_curtime = myhdl_temptime;
    
    sigset_to_update(datain);
    
    bufptr = &(buf[nbytes]);
    for(i = 0; i < cosim_ts_count; i++) {
        if(cosim_to_set[i].flags & FLAG_HAS_CHANGED) {
            // convert value to string
            if(std_logic_vector_to_string(cosim_to_set[i].ptrvector, &(cosim_to_set[i].bounds), NULL, val, MAX_STRING) < 0) {
                debug("VHPI: String conversion error on signal %s\n", cosim_to_set[i].name);
                return UPDATE_ERROR;
            }
            nbytes += snprintf(bufptr, MAX_STRING - nbytes, "%s %s ", cosim_to_set[i].name, val);
            bufptr = &(buf[nbytes]);
            cosim_to_set[i].flags &= ~FLAG_HAS_CHANGED;
            debug("VHPI: signal %s has changed.\n", cosim_to_set[i].name);
        }
    }
    
    nbytes = sendrecv(buf, MAX_STRING);
    if(nbytes < 0) {
        return UPDATE_ERROR;
    }
    if(nbytes == 0) {
        debug("VHPI: MyHDL pipe closed.\n");
        return UPDATE_END;
    }
    
    // check results back, probably put in FROM signal set
    // format: <time> [<data-1> ... <data-n>]
    
    token = strtok_r(buf, " ", &bufptr);
    sscanf(token, "%llu", (unsigned long long *) &myhdl_temptime);
    debug("VHPI: cur_myhdl_time = %lld , next_myhdl_time = %lld\n", (unsigned long long) myhdl_curtime, (unsigned long long) myhdl_temptime);
    
    for(i = 0; i < cosim_fs_count; i++) {
        token = strtok_r(NULL, " ", &bufptr);
        if(token == NULL) {
            break;
        }
        // save data
        for(j = 0, k = strlen(token); k >= 0; k--) {
            retval = hex_to_int(token[k]);
            if(retval < 0) {
                continue;
            }
            for(l = 0; l < 4; l++, j++) {
                if(retval & 0x1) {
                    val[j] = STD_LOGIC_VAL1;
                } else {
                    val[j] = STD_LOGIC_VAL0;
                }
                retval >>= 1;
            }
        }
        // account for additional zeros
        for(; j < cosim_from_set[i].bounds.len; j++) {
            val[j] = STD_LOGIC_VAL0;
        }
        // val has binary info. Update dataout vector
        if(dataout->bounds->dir) {
            // downto
            for(j = 0, k = cosim_from_set[i].bounds.right; k <= cosim_from_set[i].bounds.left; j++, k++) {
                dataout->base[(dataout->bounds->len - 1) - k] = val[j];
            }
        } else {
            // to
            for(j = 0, k = cosim_from_set[i].bounds.left; k <= cosim_from_set[i].bounds.right; j++, k++) {
                dataout->base[k] = val[j];
            }
        }
    }
    
    d_print_sigset(cosim_from_set, cosim_fs_count, "FROM_set");
    
    // put in dataout
    if(i == 0) {
        debug("VHPI: no update from myhdl.\n");
        retval = UPDATE_DELTA;
    } else {
        debug("VHPI: update %d signals from myhdl.\n", cosim_fs_count);
        // hack: VHDL time may be ahead of MyHDL time.
        // if that's the case, return UPDATE_DELTA until MyHDL time 
        // make its advance.
        if(myhdl_temptime < myhdl_curtime) {
            debug("VHPI: myhdl time retarded from vhdl time.\n");
            retval = UPDATE_DELTA;
        } else {
            retval = UPDATE_SIGNAL;
        }
    }
    
    d_print_rawdata(dataout, "dataout");
    
    // time check
    if(myhdl_temptime > myhdl_curtime) {
        debug("VHPI: myhdl call for time step to %llu.\n", (unsigned long long) myhdl_temptime);
        myhdl_next_trigger = myhdl_temptime;
        retval = UPDATE_TIME;
    }
    
    // hack: force update outputs on time 0 
    if((retval == UPDATE_DELTA) && (vhdl_curtime == 0)) {
        for(i = 0; i < cosim_ts_count; i++) {
            if(cosim_to_set[i].flags & FLAG_INITIAL_VAL) {
                cosim_to_set[i].flags |= FLAG_HAS_CHANGED;
                cosim_to_set[i].flags &= ~FLAG_INITIAL_VAL;
            }
        }
    }
    
    debug("VHPI: update_signal: return %d\n", retval);
    
    return retval;
}
/** next_timetrigger
 * calculate delay value until next delay time event
 * @param time : current VHDL time
 * @return delay value to use on a "wait for" statement
 * 
 */
  
uint64_t next_timetrigger(uint64_t time)
{
    uint64_t myhdl_temptime, delta;
    
    myhdl_temptime = time / vhdl_time_res;
    
    debug("VHPI: next_timetrigger: temp_time %llu\n", (unsigned long long) myhdl_temptime);
    
    if(myhdl_next_trigger > myhdl_temptime) {
        delta = (myhdl_next_trigger - myhdl_temptime) * vhdl_time_res;
        debug("VHPI: next_timetrigger: next VHDL trigger in %llu\n", (unsigned long long) delta);
        return delta;
    } else {
        // wait for smallest time step => 1-step in MyHDL
        return vhdl_time_res;
    }
}
