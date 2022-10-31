from pyteal import *
from pyteal.ast.bytes import Bytes
from pyteal_helpers import program

def approval():
    local_opponent = Bytes("opponent")
    local_wager = Bytes("wager")
    local_commitment = Bytes("commitment")
    local_reveal = Bytes("reveal")

    op_challenge = Bytes("challenge")
    op_accept = Bytes("accept")
    op_reveal = Bytes("reveal")

    @Subroutine(TealType.none)
    def reset(account: Expr):
        return Seq(
            App.localPut(account, local_opponent, Bytes("")),
            App.localPut(account, local_wager, Int(0)),
            App.localPut(account, local_commitment, Bytes("")),
            App.localPut(account, local_reveal, Bytes(""))
        )

    @Subroutine(TealType.uint64)
    def is_empty(account: Expr):
        return Return(
            And(
                App.localGet(account, local_opponent) == Bytes(""),
                App.localGet(account, local_wager) == Int(0),
                App.localGet(account, local_commitment) == Bytes(""),
                App.localGet(account, local_reveal) == Bytes(""),
            )
        )

    
    @Subroutine(TealType.none)
    def create_challenge():
        return Seq(
            program.check_self(
                group_size=Int(2),
                group_index=Int(0),
            ),
            program.check_rekey_zero(2),
            Assert(
                And(
                    Gtxn[1].type_enum() == TxnType.Payment,
                    #Gtxn[1].receiver() == Global.current_application_address(),
                    Gtxn[1].close_remainder_to() == Global.zero_address(),

                    App.optedIn(Txn.accounts[1], Global.current_application_id()),
                    is_empty(Txn.sender()),
                    is_empty(Txn.accounts[1]),

                    Txn.application_args.length() == Int(2),
                ),
            ),
            App.localPut(Txn.sender(), local_opponent, Txn.accounts[1]),
            App.localPut(Txn.sender(), local_wager, Gtxn[1].amount()),
            App.localPut(Txn.sender(), local_commitment, Txn.application_args[1]),
            Approve(),
        )

    @Subroutine(TealType.uint64)
    def is_valid_play(play: Expr):
        first_character = ScratchVar(TealType.bytes)
        return Seq(
            first_character.store(Substring(play, Int(0), Int(1))),
            Return(
                Or(
                    first_character.load() == Bytes("r"),
                    first_character.load() == Bytes("p"),
                    first_character.load() == Bytes("s"),
                )
            ),
        )

    @Subroutine(TealType.none)
    def accept_challenge():
        return Seq(
            program.check_self(
                group_size=Int(2),
                group_index=Int(0),
            ),
            program.check_rekey_zero(2),
            Assert(
                And(
                    App.optedIn(Txn.accounts[1], Global.current_application_id()),

                    App.localGet(Txn.accounts[1], local_opponent) == Txn.sender(),

                    Gtxn[1].type_enum() == TxnType.Payment,
                    #Gtxn[1].receiver() == Global.current_application_address(),
                    Gtxn[1].close_remainder_to() == Global.zero_address(),
                    Gtxn[1].amount() == App.localGet(Txn.accounts[1], local_wager),

                    Txn.application_args.length() == Int(2),
                    is_valid_play(Txn.application_args[1]),
                )
            ),
            App.localPut(Txn.sender(), local_opponent, Txn.accounts[1]),
            App.localPut(Txn.sender(), local_wager, Gtxn[1].amount()),
            App.localPut(Txn.sender(), local_reveal, Txn.application_args[1]),
            Approve(),
        )

    @Subroutine(TealType.uint64)
    def play_value(play: Expr):
        first_character = ScratchVar(TealType.bytes)
        return Seq(
            first_character.store(Substring(play, Int(0), Int(1))),
            Return(
                Cond(
                    [first_character.load() == Bytes("r"), Int(0)],
                    [first_character.load() == Bytes("p"), Int(1)],
                    [first_character.load() == Bytes("s"), Int(2)],
                )
            ),
        )
    
    @Subroutine(TealType.uint64)
    def winner_account_index(challenger_play: Expr, opponent_play: Expr):
        return Return(
            Cond(
                [(opponent_play + Int(1)) % Int(3) == challenger_play, Int(0)],
                [(challenger_play + Int(1)) % Int(3) == opponent_play, Int(1)],
            )
        )
    
    @Subroutine(TealType.none)
    def send_reward(account_index: Expr, amount: Expr):
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.Payment,
                TxnField.receiver: Txn.accounts[account_index],
                TxnField.amount: amount,
                TxnField.fee: Int(0),
            }),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.none)
    def reveal():
        challenger_play = ScratchVar(TealType.uint64)
        opponent_play = ScratchVar(TealType.uint64)
        wager = ScratchVar(TealType.uint64)
        return Seq(
            program.check_self(
                group_size=Int(1),
                group_index=Int(0),
            ),
            program.check_rekey_zero(1),
            Assert(
                And(
                    App.localGet(Txn.sender(), local_opponent) == Txn.accounts[1],
                    App.localGet(Txn.accounts[1], local_opponent) == Txn.sender(),

                    App.localGet(Txn.sender(), local_wager) == App.localGet(Txn.accounts[1], local_wager),

                    App.localGet(Txn.sender(), local_commitment) != Bytes(""),

                    App.localGet(Txn.accounts[1], local_reveal) != Bytes(""),

                    Txn.application_args.length() == Int(2),
                    #Sha256(Txn.application_args[1]) == App.localGet(Txn.sender(), local_commitment)
                ),
            ),
            challenger_play.store(play_value(Txn.application_args[1])),
            opponent_play.store(play_value(App.localGet(Txn.accounts[1], local_reveal))),
            wager.store(App.localGet(Txn.sender(), local_wager)),
            If(
                challenger_play.load() == opponent_play.load(),
            )
            .Then(
                Seq(
                   send_reward(Int(0), wager.load()),
                   send_reward(Int(1), wager.load()),
                ),
            )
            .Else(
                Seq(
                    send_reward(winner_account_index(challenger_play.load(), opponent_play.load()), wager.load())
                ),
            ),
            reset(Txn.sender()),
            reset(Txn.accounts[1]),
            Approve()
        )

    @Subroutine(TealType.none)
    def reset(account: Expr):
        return Seq(
            App.localPut(account, local_opponent, Bytes("")),
            App.localPut(account, local_wager, Int(0)),
            App.localPut(account, local_commitment, Bytes("")),
            App.localPut(account, local_reveal, Bytes(""))
        )

    return program.event(
        init=Approve(),
        opt_in=Seq(
            reset(Int(0)),
            Approve(),
        ),
        no_op=Seq(
            Cond(
                [Txn.application_args[0] == op_challenge, create_challenge()],
                [Txn.application_args[0] == op_accept, accept_challenge()],
                [Txn.application_args[0] == op_reveal, reveal()],
            ),
        Reject()
        ),
    )

def clear():
    return Approve()