#include "readcline/includes/readcline.h"


void	init_terminal_data(void)
{
	char	*termtype;
	int		success;

	termtype = getenv("TERM");
	if (!termtype)
		exit(1);
	success = tgetent(0, termtype);
	if (success < 0)
		exit(1);
	if (!success)
		exit(1);
}

static void	set_input_mode(void)
{
	struct termios	tattr;

	if (!isatty(STDIN_FILENO))
		exit(1);
	tcgetattr(STDIN_FILENO, &tattr);
	tattr.c_lflag &= ~(ICANON | ECHO);
	tattr.c_cc[VMIN] = 1;
	tattr.c_cc[VTIME] = 0;
	tcsetattr(STDIN_FILENO, TCSAFLUSH, &tattr);
}

void		reset_input_mode(struct termios *s)
{
	tcsetattr(STDIN_FILENO, TCSANOW, s);
}

void		init_terminal(struct termios *s)
{
	init_terminal_data();
	tcgetattr(STDIN_FILENO, s);
	set_input_mode();
}

void	readcline_handler()
{
	struct termios saved_attr;
	init_terminal(&saved_attr);
	char *input = readcline("taskmaster> ", NULL, NULL);
	ft_putstr_fd(input, 2);
	reset_input_mode(&saved_attr);
	close(2);
	sleep(3600);
}

int main ()
{
	signal(30, readcline_handler);
	sleep(3600);
}
